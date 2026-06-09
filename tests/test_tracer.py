"""tracer.py 단위 테스트."""

import sys
import pytest
from flatten.tracer import Tracer, OracleRecord, unwrap


def test_tracer_records_calls():
    tracer = Tracer()
    with tracer:
        def sample():
            return 42
        sample()

    qualnames = [r.qualname for r in tracer.records]
    assert any("sample" in q for q in qualnames)


def test_tracer_stops_cleanly():
    tracer = Tracer()
    tracer.start()
    tracer.stop()
    # 두 번 stop 해도 에러 없음
    tracer.stop()


def test_unwrap_single():
    def inner():
        pass
    assert unwrap(inner) is inner


def test_unwrap_chain():
    def base():
        pass
    def wrapped():
        pass
    wrapped.__wrapped__ = base
    assert unwrap(wrapped) is base
