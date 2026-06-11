"""Position-based LibCST rewrite application."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from flatten.contracts import TransformPlan


class PositionRewriteTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, plans: list[TransformPlan]) -> None:
        self.plans_by_range = {
            plan.target_range: plan
            for plan in plans
            if plan.target_range and plan.verdict.is_closed
        }

    def leave_SimpleStatementLine(
        self,
        original: cst.SimpleStatementLine,
        updated: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        position = self.get_metadata(PositionProvider, original)
        for plan in self.plans_by_range.values():
            if (
                plan.strategy == "guarded_temp"
                and plan.target_call_site is not None
                and plan.target_call_site.line == position.start.line
                and len(updated.body) == 1
                and isinstance(updated.body[0], cst.Return)
                and plan.temp_receiver
                and plan.receiver_expr
            ):
                assignment = cst.SimpleStatementLine(
                    [
                        cst.Assign(
                            targets=[
                                cst.AssignTarget(
                                    cst.Name(plan.temp_receiver),
                                )
                            ],
                            value=cst.parse_expression(plan.receiver_expr),
                        )
                    ]
                )
                rewritten_return = updated.with_changes(
                    body=[updated.body[0].with_changes(value=plan.replacement)]
                )
                return cst.FlattenSentinel([assignment, rewritten_return])
        return updated

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.BaseExpression:
        position = self.get_metadata(PositionProvider, original)
        key = (
            f"{position.start.line}:{position.start.column}-"
            f"{position.end.line}:{position.end.column}"
        )
        plan = self.plans_by_range.get(key)
        if plan is None:
            return updated
        if plan.strategy == "guarded_temp":
            return updated
        return plan.replacement


def rewrite_source_with_plan(source: str, plans: list[TransformPlan]) -> str:
    wrapper = MetadataWrapper(cst.parse_module(source))
    return wrapper.visit(PositionRewriteTransformer(plans)).code
