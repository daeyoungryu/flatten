"""tracer.py 단위 테스트."""

from flatten.tracer import Tracer, trace_calls, unwrap


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


def test_tracer_uses_one_tracing_backend(monkeypatch):
    calls = []
    monkeypatch.setattr("flatten.tracer._USE_MONITORING", True)
    monkeypatch.setattr("flatten.tracer._allocate_tool_id", lambda: 5)
    monkeypatch.setattr("flatten.tracer.sys.monitoring.register_callback", lambda *args: None)
    monkeypatch.setattr("flatten.tracer.sys.monitoring.set_events", lambda *args: None)
    monkeypatch.setattr("flatten.tracer.sys.monitoring.free_tool_id", lambda *args: None)
    monkeypatch.setattr("flatten.tracer.sys.settrace", lambda handler: calls.append(handler))

    tracer = Tracer()
    tracer.start()
    tracer.stop()

    assert calls == []


def test_recursive_trace_records_each_frame_without_code_key_collision():
    def factorial(value):
        if value <= 1:
            return 1
        return value * factorial(value - 1)

    with trace_calls(factorial) as tracer:
        assert factorial(3) == 6

    records = [record for record in tracer.records if record.qualname.endswith("factorial")]
    assert [record.return_val for record in records] == [1, 2, 6]


def test_arguments_are_snapshotted_at_call_time():
    class Worker:
        def run(self, values):
            values.append("mutated")
            return len(values)

    values = ["original"]
    worker = Worker()
    with trace_calls(worker.run) as tracer:
        worker.run(values)

    record = next(r for r in tracer.records if r.qualname.endswith("Worker.run"))
    assert record.args[1] == ["original"]
    assert record.args[1] is not values


def test_selfless_function_is_not_dispatch_target():
    def plain(value):
        return value

    with trace_calls(plain) as tracer:
        plain(1)

    record = next(r for r in tracer.records if r.qualname.endswith("plain"))
    assert record.impl_class is None
    assert record.is_dispatch_target is False
