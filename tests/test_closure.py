from typing import final

import pytest

from flatten.closure import (
    ClosureChecker,
    ClosureConfig,
    ClosureVerdict,
    _state_read_evidence,
    get_all_subclasses,
)
from tests.fixtures.diamond import A, B, C, D, E


@pytest.fixture
def checker():
    return ClosureChecker()


def test_all_observed_runtime_hierarchy_is_still_not_proven_closed(checker):
    verdict = checker.check("A.process", [A, B, C, D, E])
    assert isinstance(verdict, ClosureVerdict)
    assert not verdict.is_closed
    assert any("finite runtime observation" in signal for signal in verdict.open_signals)
    assert "cannot prove closed" in verdict.rationale


def test_open_hierarchy_partial_observation(checker):
    verdict = checker.check("A.process", [B])
    assert not verdict.is_closed
    assert verdict.open_signals


def test_no_impls_returns_open(checker):
    verdict = checker.check("A.process", [])
    assert not verdict.is_closed
    assert verdict.open_signals
    assert verdict.signal == "OPEN"


def test_verdict_fields(checker):
    verdict = checker.check("B.process", [B, D, E])
    assert verdict.method_qualname == "B.process"
    assert isinstance(verdict.known_impls, list)
    assert isinstance(verdict.open_signals, list)
    assert verdict.signal in {"OPEN", "UNSAFE", "OS1", "OS2", "OS3", "OS4", "OS5"}
    assert verdict.rationale


def test_get_all_subclasses_is_recursive():
    assert set(get_all_subclasses(A)) == {B, C, D, E}


def test_os1_detects_freevars(checker):
    prefix = "x"

    class Base:
        def process(self, value):
            return prefix + value

    verdict = checker.check("Base.process", [Base])
    assert any(signal.startswith("OS1") for signal in verdict.open_signals)


def test_os2_detects_closure_cells(checker):
    state = {"prefix": "x"}

    class Base:
        def process(self, value):
            return state["prefix"] + value

    verdict = checker.check("Base.process", [Base])
    assert any(signal.startswith("OS2") for signal in verdict.open_signals)


def test_os3_detects_nonlocal(checker):
    def make_base():
        counter = 0

        class Base:
            def process(self, value):
                nonlocal counter
                counter += 1
                return value + counter

        return Base

    base = make_base()
    verdict = checker.check("Base.process", [base])
    assert any(signal.startswith("OS3") for signal in verdict.open_signals)


def test_os4_detects_instance_variable_write(checker):
    class Base:
        def process(self, value):
            self.factor = value
            return value

    verdict = checker.check("Base.process", [Base])
    assert any(signal.startswith("OS4") for signal in verdict.open_signals)


def test_os5_detects_unobserved_recursive_subclasses(checker):
    class Base:
        def process(self, value):
            return value

    class Child(Base):
        pass

    class GrandChild(Child):
        pass

    verdict = checker.check("Base.process", [Base, Child])
    assert GrandChild in get_all_subclasses(Base)
    assert any(signal.startswith("OS5") for signal in verdict.open_signals)


def test_state_read_evidence_only_records_load_fast_self_load_attr_once():
    class ReadsSelf:
        def process(self):
            return self.value + self.value

    class ReadsOther:
        def process(self, other):
            return other.value

    evidence = _state_read_evidence([ReadsSelf.process, ReadsOther.process])

    assert len(evidence) == 1
    assert "ReadsSelf.process" in evidence[0]


def test_open_signals_prevent_final_class_from_being_closed():
    prefix = "x"

    @final
    class Base:
        def process(self, value):
            return prefix + value

    checker = ClosureChecker(
        ClosureConfig(static_known_classes=frozenset({f"{Base.__module__}.{Base.__qualname__}"}))
    )

    verdict = checker.check("Base.process", [Base])

    assert not verdict.is_closed
    assert verdict.signal != "CLOSED"
    assert verdict.open_signals


def test_final_base_class_alone_can_close_when_no_open_signals():
    @final
    class Base:
        def process(self):
            return "base"

    checker = ClosureChecker(
        ClosureConfig(static_known_classes=frozenset({f"{Base.__module__}.{Base.__qualname__}"}))
    )

    verdict = checker.check("Base.process", [Base])

    assert verdict.is_closed
    assert verdict.signal == "CLOSED"
    assert verdict.rationale == "typing.final class or method"


def test_final_raw_method_alone_can_close_when_no_open_signals():
    class Base:
        @final
        def process(self):
            return "base"

    checker = ClosureChecker(
        ClosureConfig(static_known_classes=frozenset({f"{Base.__module__}.{Base.__qualname__}"}))
    )

    verdict = checker.check("Base.process", [Base])

    assert verdict.is_closed
    assert verdict.signal == "CLOSED"
    assert verdict.rationale == "typing.final class or method"
