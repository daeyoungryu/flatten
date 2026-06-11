"""tracer.py 단위 테스트."""

import types

import pytest

from flatten import tracer as tracer_module
from flatten.tracer import Tracer, _allocate_tool_id, _caller_position, trace_calls, unwrap


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
    import sys
    import types

    calls = []
    mock_monitoring = types.SimpleNamespace(
        register_callback=lambda *args: None,
        set_events=lambda *args: None,
        free_tool_id=lambda *args: None,
        events=types.SimpleNamespace(
            PY_START=1,
            PY_RETURN=2,
            NO_EVENTS=0,
        ),
    )
    monkeypatch.setattr("flatten.tracer._USE_MONITORING", True)
    monkeypatch.setattr("flatten.tracer._allocate_tool_id", lambda: 5)
    monkeypatch.setattr(sys, "monitoring", mock_monitoring, raising=False)
    monkeypatch.setattr("flatten.tracer.sys", sys)
    monkeypatch.setattr(sys, "settrace", lambda handler: calls.append(handler))

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


def test_trace_calls_does_not_record_unrelated_method_with_same_name():
    class C:
        def process(self):
            return "c"

    class D:
        def process(self):
            return "d"

    c = C()
    d = D()
    with trace_calls(C.process) as tracer:
        c.process()
        d.process()

    recorded = [record.impl_class for record in tracer.records]
    assert recorded == [C]


def test_caller_position_handles_missing_and_current_frames():
    import sys

    assert _caller_position(None) == (0, -1, -1)

    line, column, end_column = _caller_position(sys._getframe())

    assert line > 0
    assert column >= -1
    assert end_column >= -1


def test_settrace_handler_dispatches_call_return_and_ignores_exception(monkeypatch):
    tracer = Tracer()
    calls = []
    returns = []
    monkeypatch.setattr(tracer, "_record_call", lambda frame: calls.append(frame))
    monkeypatch.setattr(tracer, "_record_return", lambda frame, arg: returns.append((frame, arg)))

    frame = object()

    call_handler = tracer._settrace_handler(frame, "call", None)
    return_handler = tracer._settrace_handler(frame, "return", "value")
    exception_handler = tracer._settrace_handler(frame, "exception", RuntimeError("boom"))

    assert call_handler.__self__ is tracer
    assert return_handler.__self__ is tracer
    assert exception_handler.__self__ is tracer
    assert call_handler.__func__ is Tracer._settrace_handler
    assert return_handler.__func__ is Tracer._settrace_handler
    assert exception_handler.__func__ is Tracer._settrace_handler

    assert calls == [frame]
    assert returns == [(frame, "value")]


def test_caller_position_returns_unknown_columns_when_lasti_is_missing():
    frame = types.SimpleNamespace(
        f_lineno=123,
        f_lasti=None,
        f_code=(lambda: None).__code__,
    )

    assert _caller_position(frame) == (123, -1, -1)


def test_allocate_tool_id_falls_back_to_second_candidate(monkeypatch):
    used = []

    class Monitoring:
        def use_tool_id(self, tool_id, name):
            used.append((tool_id, name))
            if tool_id == 2:
                raise ValueError("occupied")

    monkeypatch.setattr(tracer_module, "_USE_MONITORING", True)
    monkeypatch.setattr(tracer_module, "_monitoring", lambda: Monitoring())

    assert _allocate_tool_id() == 3
    assert used == [(2, "flatten-tracer"), (3, "flatten-tracer")]


@pytest.mark.parametrize(
    ("version_info", "expected_kwargs"),
    [
        ((3, 10), {}),
        ((3, 12), {"show_caches": True}),
        ((3, 13), {"show_caches": True}),
    ],
)
def test_caller_position_version_branches(monkeypatch, version_info, expected_kwargs):
    code = (lambda: None).__code__
    calls = []
    instruction = types.SimpleNamespace(
        offset=4,
        positions=types.SimpleNamespace(col_offset=7, end_col_offset=15),
    )

    def fake_get_instructions(received_code, **kwargs):
        calls.append((received_code, kwargs))
        return [instruction]

    monkeypatch.setattr(tracer_module.sys, "version_info", version_info)
    monkeypatch.setattr(tracer_module.dis, "get_instructions", fake_get_instructions)
    frame = types.SimpleNamespace(f_lineno=9, f_lasti=4, f_code=code)

    assert _caller_position(frame) == (9, 7, 15)
    assert calls == [(code, expected_kwargs)]
