from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision
from flatten.planner import RewritePlanner
from flatten.proofs import ProofStatus, classify_rewrite_decision


def test_closed_allowed_decision_with_evidence_is_safe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=True,
        status=ClosureStatus.CLOSED,
        evidence=("receiver uniquely identified", "dynamic dispatch resolved"),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.SAFE
    assert "receiver uniquely identified" in proof.evidence


def test_unknown_decision_is_never_safe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=False,
        status=ClosureStatus.UNKNOWN,
        blockers=("type restoration failed",),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.UNKNOWN
    assert "type restoration failed" in proof.reasons


def test_unsafe_decision_is_unsafe():
    decision = RewriteDecision(
        method_qualname="A.run",
        allowed=False,
        status=ClosureStatus.UNSAFE,
        blockers=("UNSAFE: monkey patch",),
    )

    proof = classify_rewrite_decision(decision)

    assert proof.status is ProofStatus.UNSAFE


def test_planner_decisions_include_proof_status():
    verdict = ClosureVerdict(
        method_qualname="A.run",
        status=ClosureStatus.CLOSED,
        reasons=("typing.final class or method",),
        evidence=("checked static package subclasses",),
    )

    decisions = RewritePlanner(opt_in=True).decide([verdict])

    assert decisions[0].proof_status == "safe"
    assert decisions[0].proof_evidence == ("checked static package subclasses",)


def test_closed_verdict_without_evidence_is_not_rewrite_allowed():
    verdict = ClosureVerdict(
        method_qualname="A.run",
        status=ClosureStatus.CLOSED,
        reasons=("legacy closed fixture",),
    )

    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert decision.allowed is False
    assert decision.proof_status == "unknown"
    assert RewritePlanner(opt_in=True).plan(verdict, []) == []
