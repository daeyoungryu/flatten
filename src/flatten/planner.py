"""Opt-in rewrite planning layer."""

from __future__ import annotations

from collections.abc import Iterable

from flatten.collapse import collapse_source
from flatten.contracts import ClosureVerdict, TransformPlan

REWRITE_WARNING = (
    "# flatten: observed-based guess; unobserved implementations may exist"
)


class RewritePlanner:
    """Create and apply rewrite plans only when explicitly opted in."""

    def __init__(self, *, opt_in: bool = False) -> None:
        self.opt_in = opt_in

    def plan(
        self,
        verdict: ClosureVerdict,
        candidate_plans: Iterable[TransformPlan],
    ) -> list[TransformPlan]:
        if not self.opt_in:
            return []
        return [
            TransformPlan(
                plan.target_node,
                plan.replacement,
                plan.verdict,
                plan.rationale
                or "observed-based guess; unobserved implementations may exist",
                plan.target_range,
            )
            for plan in candidate_plans
        ]

    def rewrite_source(self, source: str, plans: Iterable[TransformPlan]) -> str:
        if not self.opt_in:
            raise ValueError("rewrite is disabled by default; pass opt_in=True")
        rewritten = collapse_source(source, list(plans))
        if rewritten.startswith(REWRITE_WARNING):
            return rewritten
        return f"{REWRITE_WARNING}\n{rewritten}"
