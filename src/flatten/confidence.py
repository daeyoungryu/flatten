"""Ordinal confidence scoring for closed rewrite evidence.

The returned value is not a calibrated probability. It is an ordinal score used
only for CLOSED verdicts that already passed the safety policy.
"""

from __future__ import annotations

from flatten.contracts import ClosureVerdict


def confidence_score(verdict: ClosureVerdict) -> float:
    """Return an ordinal score for CLOSED verdicts, otherwise ``0.0``."""
    if not verdict.is_closed:
        return 0.0
    if verdict.confidence:
        return verdict.confidence
    if not verdict.known_impls:
        return 0.0
    base = 0.95
    penalty = min(len(verdict.open_signals) * 0.15, 0.85)
    return max(0.0, min(1.0, base - penalty))
