"""Runtime tracing for observed polymorphic calls.

Argument snapshot policy: by default only dispatch metadata is captured. Value
snapshots are opt-in because deepcopy can be expensive and user-defined.
"""

from __future__ import annotations

import ast
import copy
import linecache
import sys
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any, NamedTuple

from flatten._utils import normalize_filename as _normalize_filename
from flatten.contracts import OracleRecord

_USE_MONITORING = sys.version_info >= (3, 12)
_TOOL_ID_CANDIDATES = tuple(range(2, 6))


class PendingCall(NamedTuple):
    qualname: str
    impl_class: type | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    call_site: str
    is_dispatch_target: bool
    caller_filename: str
    caller_lineno: int
    caller_column: int
    caller_end_column: int


def _monitoring() -> Any:
    return getattr(sys, "monitoring")  # noqa: B009


def _allocate_tool_id() -> int:
    if not _USE_MONITORING:
        raise RuntimeError("sys.monitoring is unavailable")
    monitoring = _monitoring()
    for tool_id in _TOOL_ID_CANDIDATES:
        try:
            monitoring.use_tool_id(tool_id, "flatten-tracer")
            return tool_id
        except ValueError:
            continue
    raise RuntimeError("no free sys.monitoring tool id available")


def _snapshot_value(value: Any, *, receiver: bool = False) -> Any:
    if receiver:
        try:
            return weakref.proxy(value)
        except TypeError:
            return value
    try:
        return copy.deepcopy(value)
    except Exception as exc:
        import warnings
        warnings.warn(
            f"flatten: snapshot failed for {type(value).__name__}: {exc}",
            stacklevel=2,
        )
        return repr(value)


class Tracer:
    """Collect OracleRecord values for Python function calls."""

    def __init__(self, target: Any | None = None, *, capture_values: bool = True) -> None:
        self.records: list[OracleRecord] = []
        self._target = unwrap(target) if target is not None else None
        self._target_code = getattr(self._target, "__code__", None)
        self._target_name = getattr(self._target_code, "co_name", None)
        self._capture_values = capture_values
        self._active = False
        self._pending: dict[int, PendingCall] = {}
        self._monitoring_frames: dict[int, Any] = {}
        self._tool_id: int | None = None

    def start(self) -> None:
        if self._active:
            return
        if _USE_MONITORING:
            self._tool_id = _allocate_tool_id()
            monitoring = _monitoring()
            monitoring.register_callback(self._tool_id, monitoring.events.PY_START, self._on_py_start)
            monitoring.register_callback(self._tool_id, monitoring.events.PY_RETURN, self._on_py_return)
            monitoring.set_events(self._tool_id, monitoring.events.PY_START | monitoring.events.PY_RETURN)
        else:
            sys.settrace(self._settrace_handler)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return
        if _USE_MONITORING and self._tool_id is not None:
            monitoring = _monitoring()
            monitoring.set_events(self._tool_id, monitoring.events.NO_EVENTS)
            monitoring.register_callback(self._tool_id, monitoring.events.PY_START, None)
            monitoring.register_callback(self._tool_id, monitoring.events.PY_RETURN, None)
            monitoring.free_tool_id(self._tool_id)
            self._tool_id = None
        else:
            sys.settrace(None)
        self._pending.clear()
        self._monitoring_frames.clear()
        self._active = False

    def _on_py_start(self, code: Any, instruction_offset: int) -> None:
        if not self._should_record(code):
            return None
        frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._monitoring_frames[id(frame)] = frame
        self._record_call(frame)
        return None

    def _on_py_return(self, code: Any, instruction_offset: int, return_val: Any) -> None:
        if not self._should_record(code):
            return None
        frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._monitoring_frames.pop(id(frame), None)
        self._record_return(frame, return_val)
        return None

    def _should_record(self, code: Any) -> bool:
        if self._target_code is None:
            return True
        return code is self._target_code

    def _find_frame_for_code(self, code: Any) -> FrameType | None:
        frame: FrameType | None = sys._getframe()
        while frame is not None:
            if frame.f_code is code:
                return frame
            frame = frame.f_back
        return None

    def _qualname_for(self, frame: Any) -> str:
        code = frame.f_code
        qualname = getattr(code, "co_qualname", None)
        if qualname is not None:
            return str(qualname)
        self_obj = frame.f_locals.get("self") or frame.f_locals.get("cls")
        cls_name = type(self_obj).__name__ if self_obj is not None else ""
        return f"{cls_name}.{code.co_name}" if cls_name else code.co_name

    def _record_call(self, frame: Any) -> None:
        code = frame.f_code
        if not self._should_record(code):
            return
        local_vars = frame.f_locals
        positional_names = code.co_varnames[: code.co_argcount]
        keyword_only_names = code.co_varnames[code.co_argcount : code.co_argcount + code.co_kwonlyargcount]
        receiver_name = positional_names[0] if positional_names else None
        receiver = local_vars.get(receiver_name) if receiver_name in {"self", "cls"} else None
        is_dispatch_target = receiver is not None
        impl_class = type(receiver) if receiver is not None else None
        caller = getattr(frame, "f_back", None)
        caller_filename = _normalize_filename(str(caller.f_code.co_filename) if caller is not None else "")
        caller_lineno, caller_column, caller_end_column = _caller_position(caller)
        if self._capture_values:
            args = tuple(
                _snapshot_value(local_vars[name], receiver=(name == receiver_name and is_dispatch_target))
                for name in positional_names
                if name in local_vars
            )
            kwargs = {name: _snapshot_value(local_vars[name]) for name in keyword_only_names if name in local_vars}
        else:
            args = ()
            kwargs = {}
        self._pending[id(frame)] = PendingCall(
            qualname=self._qualname_for(frame),
            impl_class=impl_class,
            args=args,
            kwargs=kwargs,
            call_site=f"{code.co_filename}:{code.co_firstlineno}",
            is_dispatch_target=is_dispatch_target,
            caller_filename=caller_filename,
            caller_lineno=caller_lineno,
            caller_column=caller_column,
            caller_end_column=caller_end_column,
        )

    def _record_return(self, frame: Any, return_val: Any) -> None:
        pending = self._pending.pop(id(frame), None)
        if pending is None:
            return
        self.records.append(
            OracleRecord(
                qualname=pending.qualname,
                impl_class=pending.impl_class,
                args=pending.args,
                kwargs=pending.kwargs,
                return_val=_snapshot_value(return_val) if self._capture_values else None,
                call_site=pending.call_site,
                is_dispatch_target=pending.is_dispatch_target,
                caller_filename=pending.caller_filename,
                caller_lineno=pending.caller_lineno,
                caller_column=pending.caller_column,
                caller_end_column=pending.caller_end_column,
            )
        )

    def _settrace_handler(self, frame: Any, event: str, arg: Any) -> Any:
        if event == "call":
            self._record_call(frame)
        elif event == "return":
            self._record_return(frame, arg)
        return self._settrace_handler

    def __enter__(self) -> Tracer:
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()


def unwrap(func: Any) -> Any:
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


# Module-level AST cache: filename -> parsed ast.Module
_ast_cache: dict[str, ast.Module] = {}


def _parse_file(filename: str) -> ast.Module | None:
    cached = _ast_cache.get(filename)
    if cached is not None:
        return cached
    lines = linecache.getlines(filename)
    if not lines:
        return None
    try:
        tree = ast.parse("".join(lines), filename=filename)
        _ast_cache[filename] = tree
        return tree
    except SyntaxError:
        return None


def _caller_position(frame: Any | None) -> tuple[int, int, int]:
    """Return (lineno, col_offset, end_col_offset) for the call site in *frame*.

    Uses AST source analysis -- works uniformly on Python 3.8+.
    Returns -1 for column values when source cannot be located or parsed.
    """
    if frame is None:
        return 0, -1, -1
    lineno = int(getattr(frame, "f_lineno", 0))
    if getattr(frame, "f_lasti", None) is None:
        return lineno, -1, -1
    src_filename: str = getattr(getattr(frame, "f_code", None), "co_filename", "") or ""
    if not src_filename:
        return lineno, -1, -1
    tree = _parse_file(src_filename)
    if tree is None:
        return lineno, -1, -1
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node, "lineno", None) == lineno
    ]
    if not calls:
        return lineno, -1, -1
    calls.sort(key=lambda n: getattr(n, "col_offset", 0))
    call = calls[0]
    col = getattr(call, "col_offset", None)
    end_col = getattr(call, "end_col_offset", None)
    return lineno, (-1 if col is None else col), (-1 if end_col is None else end_col)


@contextmanager
def trace_calls(fn: Any) -> Iterator[Tracer]:
    tracer = Tracer(unwrap(fn))
    with tracer:
        yield tracer
