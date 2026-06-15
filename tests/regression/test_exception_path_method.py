"""Phase 4 exception path regression: method calls that raise must still be observed."""

from __future__ import annotations

import pytest

from flatten.tracer import Tracer


class _Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}"


class _Raiser:
    def boom(self, msg: str) -> str:
        raise ValueError(msg)


def test_method_exception_path_is_observed() -> None:
    """Method that raises an exception must still produce an observation record."""
    obj = _Raiser()
    tr = Tracer(_Raiser.boom)
    tr.start()
    with pytest.raises(ValueError, match="oops"):
        obj.boom("oops")
    tr.stop()
    assert len(tr.records) == 1, (
        f"exception-path method observation lost; got {len(tr.records)} records"
    )
    rec = tr.records[0]
    assert "boom" in rec.qualname, f"unexpected qualname: {rec.qualname!r}"


def test_method_normal_and_exception_paths_both_observed() -> None:
    """Normal call + exception call both produce records when tracing a method."""
    greeter = _Greeter()
    raiser = _Raiser()

    tr_greet = Tracer(_Greeter.greet)
    tr_greet.start()
    result = greeter.greet("world")
    tr_greet.stop()
    assert result == "Hello, world"
    assert len(tr_greet.records) == 1, "normal method call not recorded"

    tr_boom = Tracer(_Raiser.boom)
    tr_boom.start()
    with pytest.raises(ValueError):
        raiser.boom("fail")
    tr_boom.stop()
    assert len(tr_boom.records) == 1, "exception-path method call not recorded"
