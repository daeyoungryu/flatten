"""Proof classification for rewrite authorization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from flatten.contracts import ClosureStatus, RewriteDecision


class ProofStatus(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProofEvidence:
    status: ProofStatus
    reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
        }


def classify_rewrite_decision(decision: RewriteDecision) -> ProofEvidence:
    if decision.allowed and decision.status is ClosureStatus.CLOSED and decision.evidence:
        return ProofEvidence(
            status=ProofStatus.SAFE,
            reasons=decision.reasons,
            evidence=decision.evidence,
        )
    if decision.status is ClosureStatus.UNSAFE:
        return ProofEvidence(
            status=ProofStatus.UNSAFE,
            reasons=decision.blockers or decision.reasons,
            evidence=decision.evidence,
        )
    return ProofEvidence(
        status=ProofStatus.UNKNOWN,
        reasons=decision.blockers or decision.reasons,
        evidence=decision.evidence,
    )
