"""sys.monitoring 기반 런타임 추적 — 어떤 다형 구현이 실제로 호출됐는지 확정."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

TOOL_ID = sys.monitoring.DEBUGGER_ID


@dataclass
class OracleRecord:
    qualname: str
    impl_class: type
    args: tuple
    kwargs: dict
    return_val: Any = None


class Tracer:
    """sys.monitoring을 사용해 함수 진입을 기록한다."""

    def __init__(self) -> None:
        self.records: list[OracleRecord] = []
        self._active = False

    def start(self) -> None:
        sys.monitoring.use_tool_id(TOOL_ID, "flatten-tracer")
        sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.PY_START)
        sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.PY_START, self._on_py_start)
        self._active = True

    def stop(self) -> None:
        if self._active:
            sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.NO_EVENTS)
            sys.monitoring.free_tool_id(TOOL_ID)
            self._active = False

    def _on_py_start(self, code, instruction_offset: int) -> None:
        qualname: str = getattr(code, "co_qualname", code.co_name)
        self.records.append(
            OracleRecord(qualname=qualname, impl_class=object, args=(), kwargs={})
        )

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
