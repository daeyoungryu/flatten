"""Runtime tracing for observed polymorphic calls."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from flatten.contracts import OracleRecord

_USE_MONITORING = sys.version_info >= (3, 12)
TOOL_ID = sys.monitoring.DEBUGGER_ID if _USE_MONITORING else None

# Separate tool ID for ExecutionTracer to avoid collision with Tracer (DEBUGGER_ID=0)
_EXEC_TRACER_TOOL_ID = 6


class ExecutionTracer:
    """Collect OracleRecord values filtered by target_classes."""

    def __init__(self, target_classes=None) -> None:
        self.target_classes = target_classes or []
        self.records: list[OracleRecord] = []

    def _record_return(self, code: Any, frame_or_none: Any, retval: Any) -> None:
        # co_qualname fallback (3.11 미만에서 co_qualname 없음)
        qualname = getattr(code, "co_qualname", None)
        if qualname is None:
            self_obj = frame_or_none.f_locals.get("self") if frame_or_none else None
            cls_name = type(self_obj).__name__ if self_obj else ""
            qualname = f"{cls_name}.{code.co_name}" if cls_name else code.co_name

        # target_classes 필터
        if self.target_classes and frame_or_none is not None:
            self_obj = frame_or_none.f_locals.get("self")
            if self_obj is None or not isinstance(self_obj, tuple(self.target_classes)):
                return

        call_site = f"{code.co_filename}:{code.co_firstlineno}"

        if frame_or_none is not None:
            local_vars = frame_or_none.f_locals
            positional_names = code.co_varnames[: code.co_argcount]
            keyword_only_names = code.co_varnames[
                code.co_argcount : code.co_argcount + code.co_kwonlyargcount
            ]
            args = tuple(
                local_vars[name] for name in positional_names if name in local_vars
            )
            kwargs = {
                name: local_vars[name]
                for name in keyword_only_names
                if name in local_vars
            }
            impl_class = args[0].__class__ if args else object
        else:
            args = ()
            kwargs = {}
            impl_class = object

        self.records.append(
            OracleRecord(
                qualname=qualname,
                impl_class=impl_class,
                args=args,
                kwargs=kwargs,
                return_val=retval,
                call_site=call_site,
            )
        )

    def _on_py_start(self, code: Any, instruction_offset: int) -> None:
        return None

    def _on_py_return(self, code: Any, instruction_offset: int, retval: Any) -> None:
        frame = sys._getframe()
        f = frame
        while f is not None:
            if f.f_code is code:
                self._record_return(code, f, retval)
                return None
            f = f.f_back
        self._record_return(code, None, retval)
        return None

    def _settrace_handler(self, frame: Any, event: str, arg: Any):
        if event == "return":
            self._record_return(frame.f_code, frame, arg)
        return self._settrace_handler

    def __enter__(self) -> "ExecutionTracer":
        if _USE_MONITORING:
            sys.monitoring.use_tool_id(_EXEC_TRACER_TOOL_ID, "flatten_tracer")
            sys.monitoring.register_callback(
                _EXEC_TRACER_TOOL_ID,
                sys.monitoring.events.PY_START,
                self._on_py_start,
            )
            sys.monitoring.register_callback(
                _EXEC_TRACER_TOOL_ID,
                sys.monitoring.events.PY_RETURN,
                self._on_py_return,
            )
            sys.monitoring.set_events(
                _EXEC_TRACER_TOOL_ID,
                sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN,
            )
        else:
            sys.settrace(self._settrace_handler)
        return self

    def __exit__(self, *_) -> None:
        if _USE_MONITORING:
            sys.monitoring.set_events(_EXEC_TRACER_TOOL_ID, sys.monitoring.events.NO_EVENTS)
            sys.monitoring.register_callback(_EXEC_TRACER_TOOL_ID, sys.monitoring.events.PY_START, None)
            sys.monitoring.register_callback(_EXEC_TRACER_TOOL_ID, sys.monitoring.events.PY_RETURN, None)
            sys.monitoring.free_tool_id(_EXEC_TRACER_TOOL_ID)
        else:
            sys.settrace(None)


class Tracer:
    """Collect OracleRecord values for Python function calls."""

    def __init__(self, target: Any | None = None) -> None:
        self.records: list[OracleRecord] = []
        self._target = unwrap(target) if target is not None else None
        self._target_code = getattr(self._target, "__code__", None)
        self._target_name = getattr(self._target_code, "co_name", None)
        self._active = False
        self._pending: dict[Any, tuple[str, type, tuple, dict, str]] = {}
        self._monitoring_frames: dict[Any, Any] = {}

    def start(self) -> None:
        if self._active:
            return

        if _USE_MONITORING:
            sys.monitoring.use_tool_id(TOOL_ID, "flatten-tracer")
            sys.monitoring.register_callback(
                TOOL_ID, sys.monitoring.events.PY_START, self._on_py_start
            )
            sys.monitoring.register_callback(
                TOOL_ID, sys.monitoring.events.PY_RETURN, self._on_py_return
            )
            sys.monitoring.set_events(
                TOOL_ID,
                sys.monitoring.events.PY_START | sys.monitoring.events.PY_RETURN,
            )

        sys.settrace(self._settrace_handler)
        self._active = True

    def stop(self) -> None:
        if not self._active:
            return

        sys.settrace(None)
        if _USE_MONITORING:
            sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
            sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, None)
            sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_RETURN, None)
            sys.monitoring.free_tool_id(TOOL_ID)

        self._pending.clear()
        self._active = False

    def _on_py_start(self, code: Any, instruction_offset: int) -> None:
        frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._monitoring_frames[code] = frame
        self._record_call(frame)
        return None

    def _on_py_return(self, code: Any, instruction_offset: int, return_val: Any) -> None:
        frame = self._monitoring_frames.pop(code, None)
        if frame is None:
            frame = self._find_frame_for_code(code)
        if frame is None:
            return None
        self._record_return(frame, return_val)
        return None

    def _should_record(self, code: Any) -> bool:
        if self._target_code is None:
            return True
        return code is self._target_code or code.co_name == self._target_name

    def _find_frame_for_code(self, code: Any) -> Any | None:
        frame = sys._getframe()
        while frame is not None:
            if frame.f_code is code:
                return frame
            frame = frame.f_back
        return None

    def _qualname_for(self, frame: Any) -> str:
        code = frame.f_code
        qualname = getattr(code, "co_qualname", None)
        if qualname is not None:
            return qualname
        self_obj = frame.f_locals.get("self")
        cls_name = type(self_obj).__name__ if self_obj else ""
        return f"{cls_name}.{code.co_name}" if cls_name else code.co_name

    def _record_call(self, frame: Any) -> None:
        code = frame.f_code
        if not self._should_record(code):
            return

        qualname = self._qualname_for(frame)
        call_site = f"{code.co_filename}:{code.co_firstlineno}"
        local_vars = frame.f_locals
        positional_names = code.co_varnames[: code.co_argcount]
        keyword_only_names = code.co_varnames[
            code.co_argcount : code.co_argcount + code.co_kwonlyargcount
        ]
        args = tuple(local_vars[name] for name in positional_names if name in local_vars)
        kwargs = {
            name: local_vars[name] for name in keyword_only_names if name in local_vars
        }
        impl_class = args[0].__class__ if args else object
        self._pending[frame] = (qualname, impl_class, args, kwargs, call_site)

    def _record_return(self, frame: Any, return_val: Any) -> None:
        pending = self._pending.pop(frame, None)
        if pending is None:
            return

        qualname, impl_class, args, kwargs, call_site = pending
        self.records.append(
            OracleRecord(
                qualname=qualname,
                impl_class=impl_class,
                args=args,
                kwargs=kwargs,
                return_val=return_val,
                call_site=call_site,
            )
        )

    def _settrace_handler(self, frame: Any, event: str, arg: Any):
        if event == "call":
            self._record_call(frame)
        elif event == "return":
            self._record_return(frame, arg)
        return self._settrace_handler

    def __enter__(self) -> "Tracer":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


def unwrap(func):
    """Return the original function at the end of a __wrapped__ chain."""
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


@contextmanager
def trace_calls(fn) -> Iterator[Tracer]:
    tracer = Tracer(unwrap(fn))
    with tracer:
        yield tracer
