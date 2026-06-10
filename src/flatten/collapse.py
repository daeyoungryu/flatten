"""LibCST transforms that collapse planned call sites."""

from __future__ import annotations

from collections.abc import Iterable

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from flatten.contracts import TransformPlan


class CollapseTransformer(cst.CSTTransformer):
    """Apply a batch of TransformPlan replacements while preserving structure."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, plans: Iterable[TransformPlan] | set[str]) -> None:
        if isinstance(plans, set):
            raise ValueError("unsafe inline path is not supported")
        self._plans = list(plans) if not isinstance(plans, set) else []
        self._plans_by_range = {
            plan.target_range: plan for plan in self._plans if plan.target_range
        }

    def visit_Assign(self, node: cst.Assign) -> bool:
        return True

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        for plan in self._plans:
            if original is plan.target_node:
                return plan.replacement
        if hasattr(self, "metadata"):
            position = self.get_metadata(PositionProvider, original, None)
        else:
            position = None
        if position is not None:
            key = (
                f"{position.start.line}:{position.start.column}-"
                f"{position.end.line}:{position.end.column}"
            )
            matched_plan = self._plans_by_range.get(key)
            if matched_plan is not None:
                return matched_plan.replacement
        return updated

    def leave_Name(self, original: cst.Name, updated: cst.Name) -> cst.BaseExpression:
        return updated


def collapse_source(source: str, plans: Iterable[TransformPlan] | set[str]) -> str:
    if isinstance(plans, set):
        raise ValueError("unsafe inline path is not supported")
    tree = MetadataWrapper(cst.parse_module(source))
    transformer = CollapseTransformer(plans)
    return tree.visit(transformer).code
