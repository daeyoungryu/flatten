"""Confidence scoring for observed dispatch analysis."""

from __future__ import annotations

from flatten.contracts import ClosureVerdict


def confidence_score(verdict: ClosureVerdict) -> float:
    if not verdict.known_impls:
        return 0.0
    penalty = min(len(verdict.open_signals) * 0.15, 0.85)
    return max(0.0, min(1.0, 0.75 - penalty))
