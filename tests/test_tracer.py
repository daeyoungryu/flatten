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


def test_record_call_reconstructs_qualname_without_co_qualname():
    class LegacyCode:
        co_name = "run"
        co_argcount = 1
        co_kwonlyargcount = 0
        co_varnames = ("self",)
        co_filename = "legacy.py"
        co_firstlineno = 12

    class Frame:
        f_code = LegacyCode()

        class Worker:
            pass

        f_locals = {"self": Worker()}

    tracer = Tracer()
    frame = Frame()
    tracer._record_call(frame)
    tracer._record_return(frame, "ok")

    record = tracer.records[0]
    assert record.qualname == "Worker.run"
    assert record.call_site == "legacy.py:12"


def test_contracts_expose_added_fields():
    class Worker:
        def run(self):
            return "ok"

    with trace_calls(Worker().run) as tracer:
        Worker().run()

    record = next(r for r in tracer.records if r.qualname.endswith("Worker.run"))
    assert hasattr(record, "call_site")
    assert record.call_site


def test_monitoring_callbacks_complete_oracle_record(monkeypatch):
    class Worker:
        def run(self):
            return "ok"

    worker = Worker()

    class Frame:
        f_code = Worker.run.__code__
        f_locals = {"self": worker}

    frame = Frame()
    tracer = Tracer(Worker.run)
    monkeypatch.setattr(tracer, "_find_frame_for_code", lambda code: frame)

    tracer._on_py_start(Worker.run.__code__, 0)
    tracer._on_py_return(Worker.run.__code__, 0, "ok")

    assert len(tracer.records) == 1
    record = tracer.records[0]
    assert record.impl_class is Worker
    assert record.return_val == "ok"
    assert record.call_site.endswith(f"test_tracer.py:{Worker.run.__code__.co_firstlineno}")
