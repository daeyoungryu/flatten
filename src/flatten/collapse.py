"""LibCST transforms that collapse planned call sites."""

from __future__ import annotations

from collections.abc import Iterable

import libcst as cst

from flatten.contracts import TransformPlan


class CollapseTransformer(cst.CSTTransformer):
    """Apply a batch of TransformPlan replacements while preserving structure."""

    def __init__(self, plans: Iterable[TransformPlan] | set[str]) -> None:
        self._plans = list(plans) if not isinstance(plans, set) else []
        self._inline_targets = plans if isinstance(plans, set) else set()
        self._bindings: dict[str, cst.BaseExpression] = {}

    def visit_Assign(self, node: cst.Assign) -> bool:
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                if target.target.value in self._inline_targets:
                    self._bindings[target.target.value] = node.value
        return True

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.CSTNode:
        for plan in self._plans:
            if original is plan.target_node or original.deep_equals(plan.target_node):
                return plan.replacement
        return updated

    def leave_Name(self, original: cst.Name, updated: cst.Name) -> cst.CSTNode:
        if updated.value in self._bindings:
            return self._bindings[updated.value]
        return updated


def collapse_source(source: str, plans: Iterable[TransformPlan] | set[str]) -> str:
    tree = cst.parse_module(source)
    transformer = CollapseTransformer(plans)
    return tree.visit(transformer).code
