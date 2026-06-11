import pytest

from flatten.closure import ClosureChecker
from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision
from flatten.planner import RewritePlanner


def test_forcing_open_verdict_to_closed_would_fail_sibling_safety_assertion():
    class Base:
        def run(self):
            return "base"

    class A(Base):
        def run(self):
            return "a"

    class B(Base):
        def run(self):
            return "b"

    verdict = ClosureChecker().check("Base.run", [A])
    mutated = ClosureVerdict(
        verdict.method_qualname,
        known_impls=verdict.known_impls,
        status=ClosureStatus.CLOSED,
        evidence=("mutated",),
    )

    with pytest.raises(AssertionError):
        assert mutated.status is not ClosureStatus.CLOSED
    assert verdict.status is not ClosureStatus.CLOSED


def test_receiver_type_omission_is_defended_by_reason_code():
    decision = RewriteDecision.from_verdict(
        ClosureVerdict(
            "Base.run",
            known_impls=[],
            status=ClosureStatus.OPEN,
            blockers=("no observed impls",),
        )
    )

    assert decision.allowed is False
    assert decision.reason_code == "UNSAFE_NO_RECEIVER_TYPES"


def test_dynamic_getattr_allowed_mutation_would_fail():
    class Dynamic:
        def __getattr__(self, name):
            raise AttributeError(name)

        def run(self):
            return 1

    verdict = ClosureChecker().check("Dynamic.run", [Dynamic])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    with pytest.raises(AssertionError):
        assert decision.allowed is True
    assert decision.reason_code == "UNSAFE_DYNAMIC_GETATTR"


def test_multiple_inheritance_allowed_mutation_would_fail():
    class Left:
        def run(self):
            return "left"

    class Right:
        def run(self):
            return "right"

    class Both(Left, Right):
        pass

    decision = RewritePlanner(opt_in=True).decide(
        [ClosureChecker().check("Left.run", [Both])]
    )[0]

    with pytest.raises(AssertionError):
        assert decision.allowed is True
    assert decision.reason_code == "UNSAFE_MULTIPLE_INHERITANCE"
