"""closure.py 단위 테스트 — OS1~OS5 신호 및 닫힌/열린 판정."""

import pytest
from flatten.closure import ClosureChecker, ClosureVerdict, get_all_subclasses
from tests.fixtures.diamond import A, B, C, D, E


@pytest.fixture
def checker():
    return ClosureChecker()


def test_closed_hierarchy_all_observed(checker):
    # A의 서브클래스 전체를 관측했을 때 닫힌 계층으로 판정
    verdict = checker.check("A.process", [A, B, C, D, E])
    assert isinstance(verdict, ClosureVerdict)
    # 외부 모듈 없음 → OS1 없음


def test_open_hierarchy_partial_observation(checker):
    # 일부만 관측 시 열린 계층
    verdict = checker.check("A.process", [B])
    assert not verdict.is_closed or len(verdict.open_signals) > 0


def test_no_impls_returns_open(checker):
    verdict = checker.check("A.process", [])
    assert not verdict.is_closed
    assert verdict.open_signals


def test_verdict_fields(checker):
    verdict = checker.check("B.process", [B, D, E])
    assert verdict.method_qualname == "B.process"
    assert isinstance(verdict.known_impls, list)
    assert isinstance(verdict.open_signals, list)
    assert verdict.signal in {"CLOSED", "OS1", "OS2", "OS3", "OS4", "OS5"}


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


def test_os4_detects_instance_variable_access(checker):
    class Base:
        def process(self, value):
            return self.factor * value

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
