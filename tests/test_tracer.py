"""tracer.py 단위 테스트."""

import pytest
from flatten.tracer import Tracer, OracleRecord, trace_calls, unwrap


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


def test_trace_calls_records_impl_class_args_kwargs_and_return_value():
    class Worker:
        def run(self, value, *, scale=1):
            return value * scale

    worker = Worker()
    with trace_calls(worker.run) as tracer:
        assert worker.run(7, scale=3) == 21

    record = next(r for r in tracer.records if r.qualname.endswith("Worker.run"))
    assert record.impl_class is Worker
    assert record.args == (worker, 7)
    assert record.kwargs == {"scale": 3}
    assert record.return_val == 21
    assert record.call_site.endswith(f"test_tracer.py:{Worker.run.__code__.co_firstlineno}")


def test_trace_calls_unwraps_wrapped_function():
    def original(self):
        return "original"

    def wrapper(self):
        return original(self)

    wrapper.__wrapped__ = original

    class Wrapped:
        run = wrapper

    instance = Wrapped()
    with trace_calls(instance.run) as tracer:
        assert instance.run() == "original"

    record = next(r for r in tracer.records if r.qualname.endswith("original"))
    assert record.impl_class is Wrapped
    assert record.return_val == "original"
