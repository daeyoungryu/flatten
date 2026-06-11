"""Reproducible evaluation metrics for flatten rewrite decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCounts:
    total_call_sites: int = 0
    candidate_call_sites: int = 0
    rewritten_call_sites: int = 0
    rejected_call_sites: int = 0
    unsafe_call_sites: int = 0
    unknown_call_sites: int = 0

    def to_json(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class LabeledOutcome:
    expected_safe: bool
    rewritten: bool


@dataclass(frozen=True)
class EvaluationMetrics:
    counts: EvaluationCounts
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None

    def to_json(self) -> dict[str, Any]:
        return {
            "counts": self.counts.to_json(),
            "precision": self.precision,
            "recall": self.recall,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def compute_metrics(
    counts: EvaluationCounts,
    outcomes: list[LabeledOutcome],
) -> EvaluationMetrics:
    true_positive = sum(1 for item in outcomes if item.expected_safe and item.rewritten)
    false_positive = sum(1 for item in outcomes if not item.expected_safe and item.rewritten)
    false_negative = sum(1 for item in outcomes if item.expected_safe and not item.rewritten)
    true_negative = sum(1 for item in outcomes if not item.expected_safe and not item.rewritten)
    return EvaluationMetrics(
        counts=counts,
        precision=_rate(true_positive, true_positive + false_positive),
        recall=_rate(true_positive, true_positive + false_negative),
        false_positive_rate=_rate(false_positive, false_positive + true_negative),
        false_negative_rate=_rate(false_negative, false_negative + true_positive),
    )
