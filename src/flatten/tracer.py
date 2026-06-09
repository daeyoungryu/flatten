"""런타임 추적 — 어떤 다형 구현이 실제로 호출됐는지 확정.

Python 버전별 동작:
- 3.12+: sys.monitoring (PY_START 이벤트) 사용. 오버헤드 낮음.
- 3.8~3.11: sys.settrace fallback 사용. co_qualname 없는 경우 co_name으로 대체.
"""

from __future__ import annotations

import sys
from typing import Any

from flatten.contracts import OracleRecord

_USE_MONITORING = sys.version_info >= (3, 12)
TOOL_ID = sys.monitoring.DEBUGGER_ID if _USE_MONITORING else None


class Tracer:
    """함수 진입을 기록한다. 3.12+는 sys.monitoring, 3.8~3.11은 sys.settrace."""

    def __init__(self) -> None:
        self.records: list[OracleRecord] = []
        self._active = False

    def start(self) -> None:
        if _USE_MONITORING:
            sys.monitoring.use_tool_id(TOOL_ID, "flatten-tracer")
            sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.PY_START)
            sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, self._on_py_start)
        else:
            sys.settrace(self._settrace_handler)
        self._active = True

    def stop(self) -> None:
        if self._active:
            if _USE_MONITORING:
                sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
                sys.monitoring.free_tool_id(TOOL_ID)
            else:
                sys.settrace(None)
            self._active = False

    def _on_py_start(self, code, instruction_offset: int) -> None:
        qualname: str = getattr(code, "co_qualname", code.co_name)
        self.records.append(
            OracleRecord(qualname=qualname, impl_class=object, args=(), kwargs={})
        )

    def _settrace_handler(self, frame, event: str, arg: Any):
        if event == "call":
            code = frame.f_code
            qualname: str = getattr(code, "co_qualname", code.co_name)
            self.records.append(
                OracleRecord(qualname=qualname, impl_class=object, args=(), kwargs={})
            )
        return self._settrace_handler

    def __enter__(self) -> "Tracer":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


def unwrap(func):
    """__wrapped__ 체인을 끝까지 풀어 원본 함수를 반환한다."""
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func
