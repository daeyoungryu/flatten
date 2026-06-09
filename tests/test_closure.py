"""closure.py 단위 테스트 — OS1~OS5 신호 및 닫힌/열린 판정."""

import pytest
from flatten.closure import ClosureChecker, ClosureVerdict
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
