"""Runtime tracing for observed polymorphic calls.

Argument snapshot policy: call arguments are captured at call time. The receiver
(`self`/`cls`) is stored as a weak proxy when possible; other values use
`copy.deepcopy` with a bounded `repr` fallback. Records without a receiver are
marked `is_dispatch_target=False`.
"""

from __future__ import annotations

import copy
import sys
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

from flatten.contracts import OracleRecord

_USE_MONITORING = sys.version_info >= (3, 12)
_TOOL_ID_CANDIDATES = tuple(range(2, 6))


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
    except Exception:
        return repr(value)


class Tracer:
    """Collect OracleRecord values for Python function calls."""

    def __init__(self, target: Any | None = None) -> None:
        self.records: list[OracleRecord] = []
        self._target = unwrap(target) if target is not None else None
        self._target_code = getattr(self._target, "__code__", None)
        self._target_name = getattr(self._target_code, "co_name", None)
        self._active = False
        self._pending: dict[
            int,
            tuple[str, type | None, tuple[Any, ...], dict[str, Any], str, bool],
        ] = {}
        self._monitoring_frames: dict[int, Any] = {}
        self._tool_id: int | None = None

    def start(self) -> None:
        if self._active:
            return

        if _USE_MONITORING:
            self._tool_id = _allocate_tool_id()
            monitoring = _monitoring()
            monitoring.register_callback(
                self._tool_id, monitoring.events.PY_START, self._on_py_start
            )
            monitoring.register_callback(
                self._tool_id, monitoring.events.PY_RETURN, self._on_py_return
            )
            monitoring.set_events(
                self._tool_id,
                monitoring.events.PY_START | monitoring.events.PY_RETURN,
            )
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
        frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._monitoring_frames[id(frame)] = frame
        self._record_call(frame)
        return None

    def _on_py_return(self, code: Any, instruction_offset: int, return_val: Any) -> None:
        frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._monitoring_frames.pop(id(frame), None)
        self._record_return(frame, return_val)
        return None

    def _should_record(self, code: Any) -> bool:
        if self._target_code is None:
            return True
        return code is self._target_code or code.co_name == self._target_name

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
        keyword_only_names = code.co_varnames[
            code.co_argcount : code.co_argcount + code.co_kwonlyargcount
        ]
        receiver_name = positional_names[0] if positional_names else None
        receiver = (
            local_vars.get(receiver_name)
            if receiver_name in {"self", "cls"}
            else None
        )
        is_dispatch_target = receiver is not None
        impl_class = type(receiver) if receiver is not None else None

        args = tuple(
            _snapshot_value(
                local_vars[name],
                receiver=(name == receiver_name and is_dispatch_target),
            )
            for name in positional_names
            if name in local_vars
        )
        kwargs = {
            name: _snapshot_value(local_vars[name])
            for name in keyword_only_names
            if name in local_vars
        }
        self._pending[id(frame)] = (
            self._qualname_for(frame),
            impl_class,
            args,
            kwargs,
            f"{code.co_filename}:{code.co_firstlineno}",
            is_dispatch_target,
        )

    def _record_return(self, frame: Any, return_val: Any) -> None:
        pending = self._pending.pop(id(frame), None)
        if pending is None:
            return

        qualname, impl_class, args, kwargs, call_site, is_dispatch_target = pending
        self.records.append(
            OracleRecord(
                qualname=qualname,
                impl_class=impl_class,
                args=args,
                kwargs=kwargs,
                return_val=_snapshot_value(return_val),
                call_site=call_site,
                is_dispatch_target=is_dispatch_target,
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
    """Return the original function at the end of a __wrapped__ chain."""
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


@contextmanager
def trace_calls(fn: Any) -> Iterator[Tracer]:
    tracer = Tracer(unwrap(fn))
    with tracer:
        yield tracer
