"""Runtime tracing for observed polymorphic calls."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from flatten.contracts import OracleRecord

_USE_MONITORING = sys.version_info >= (3, 12)
TOOL_ID = sys.monitoring.DEBUGGER_ID if _USE_MONITORING else None


class Tracer:
    """Collect OracleRecord values for Python function calls."""

    def __init__(self, target: Any | None = None) -> None:
        self.records: list[OracleRecord] = []
        self._target = unwrap(target) if target is not None else None
        self._target_code = getattr(self._target, "__code__", None)
        self._target_name = getattr(self._target_code, "co_name", None)
        self._active = False
        self._pending: dict[Any, tuple[str, type, tuple, dict]] = {}

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
            sys.monitoring.register_callback(
                TOOL_ID, sys.monitoring.events.PY_START, None
            )
            sys.monitoring.register_callback(
                TOOL_ID, sys.monitoring.events.PY_RETURN, None
            )
            sys.monitoring.free_tool_id(TOOL_ID)

        self._pending.clear()
        self._active = False

    def _on_py_start(self, code: Any, instruction_offset: int) -> None:
        return None

    def _on_py_return(
        self, code: Any, instruction_offset: int, return_val: Any
    ) -> None:
        return None

    def _should_record(self, code: Any) -> bool:
        if self._target_code is None:
            return True
        return code is self._target_code or code.co_name == self._target_name

    def _record_call(self, frame: Any) -> None:
        code = frame.f_code
        if not self._should_record(code):
            return

        qualname: str = getattr(code, "co_qualname", code.co_name)
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
        self._pending[frame] = (qualname, impl_class, args, kwargs)

    def _record_return(self, frame: Any, return_val: Any) -> None:
        pending = self._pending.pop(frame, None)
        if pending is None:
            return

        qualname, impl_class, args, kwargs = pending
        self.records.append(
            OracleRecord(
                qualname=qualname,
                impl_class=impl_class,
                args=args,
                kwargs=kwargs,
                return_val=return_val,
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
