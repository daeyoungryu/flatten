from flatten.contracts import ClosureStatus, RewriteDecision
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
