"""Behavior comparison API for original and rewritten callables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flatten.harness import BehaviorObservation, capture_behavior


@dataclass(frozen=True)
class BehaviorMismatch:
    case_index: int
    field: str
    original: str
    transformed: str


@dataclass(frozen=True)
class BehaviorComparisonResult:
    equivalent: bool
    cases: int
    mismatches: list[BehaviorMismatch]

    def to_json(self) -> dict[str, Any]:
        return {
            "equivalent": self.equivalent,
            "cases": self.cases,
            "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
        }


class BehaviorComparator:
    def compare(
        self,
        original: Callable[..., Any],
        transformed: Callable[..., Any],
        cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> BehaviorComparisonResult:
        mismatches: list[BehaviorMismatch] = []
        for index, (args, kwargs) in enumerate(cases):
            left = capture_behavior(original, *args, **kwargs)
            right = capture_behavior(transformed, *args, **kwargs)
            mismatches.extend(_compare_observation(index, left, right))
        return BehaviorComparisonResult(
            equivalent=not mismatches,
            cases=len(cases),
            mismatches=mismatches,
        )


def _compare_observation(
    index: int,
    original: BehaviorObservation,
    transformed: BehaviorObservation,
) -> list[BehaviorMismatch]:
    mismatches: list[BehaviorMismatch] = []
    if original.outcome != transformed.outcome:
        return [
            BehaviorMismatch(index, "outcome", original.outcome, transformed.outcome)
        ]
    if original.outcome == "raise":
        left = f"{original.exception_type}: {original.exception_message}"
        right = f"{transformed.exception_type}: {transformed.exception_message}"
        if left != right:
            mismatches.append(BehaviorMismatch(index, "exception", left, right))
    elif original.value != transformed.value:
        mismatches.append(
            BehaviorMismatch(index, "return", repr(original.value), repr(transformed.value))
        )
    if original.effects != transformed.effects:
        mismatches.append(
            BehaviorMismatch(index, "effects", repr(original.effects), repr(transformed.effects))
        )
    return mismatches
