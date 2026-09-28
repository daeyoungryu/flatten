import sys
import pytest
from flatten.harness import capture_behavior


def test_return_path_effects_and_order():
    def f(a, b=1):
        print("out")
        print("err", file=sys.stderr)
        return a + b

    o = capture_behavior(f, 1, b=2, effect_collectors={"n": lambda: 5, "m": lambda: "z"})
    assert (o.outcome, o.value) == ("return", 3)
    assert o.exception_type is None and o.exception_message is None
    assert o.effects == {"stdout": "out\n", "stderr": "err\n", "n": 5, "m": "z"}
    assert list(o.effects) == ["stdout", "stderr", "n", "m"]


def test_raise_path_effects_and_order():
    def f():
        print("partial")
        print("perr", file=sys.stderr)
        raise KeyError("k")

    o = capture_behavior(f, effect_collectors={"n": lambda: 7})
    assert o.outcome == "raise" and o.value is None
    assert o.exception_type == "KeyError" and o.exception_message == "'k'"
    assert o.effects == {"stdout": "partial\n", "stderr": "perr\n", "n": 7}
    assert list(o.effects) == ["stdout", "stderr", "n"]


def test_qualname_of_nested_exception_class():
    class Local(Exception):
        pass

    def f():
        raise Local("x")

    o = capture_behavior(f)
    assert o.exception_type.endswith("Local") and "." in o.exception_type
    assert o.effects == {"stdout": "", "stderr": ""}


def test_no_collectors_default():
    o = capture_behavior(lambda: 1)
    assert o.effects == {"stdout": "", "stderr": ""} and o.value == 1


def test_success_collectors_called_once_each():
    calls = []
    capture_behavior(lambda: 1, effect_collectors={"c": lambda: calls.append(1) or len(calls)})
    assert calls == [1]


def test_collector_error_on_return_path_propagates():
    def boom():
        raise ValueError("collector")

    with pytest.raises(ValueError, match="collector"):
        capture_behavior(lambda: 1, effect_collectors={"c": boom})


def test_collector_error_on_raise_path_propagates():
    def boom():
        raise ValueError("collector")

    def f():
        raise RuntimeError("f")

    with pytest.raises(ValueError, match="collector"):
        capture_behavior(f, effect_collectors={"c": boom})


def test_non_exception_baseexception_not_swallowed():
    def f():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        capture_behavior(f)
