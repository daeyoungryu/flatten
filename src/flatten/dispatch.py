"""LibCST builders for flattening polymorphic dispatch."""

from __future__ import annotations

from collections.abc import Iterable

import libcst as cst

from flatten.contracts import ClosureVerdict, TransformPlan

OPEN_DISPATCH_COMMENT = "# OPEN_DISPATCH: {qualname} - unobserved impls possible"


class DispatchTransformer(cst.CSTTransformer):
    """Replace planned call nodes with their dispatch expression."""

    def __init__(self, plans: Iterable[TransformPlan]) -> None:
        self._plans = list(plans)

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.CSTNode:
        for plan in self._plans:
            if original is plan.target_node or original.deep_equals(plan.target_node):
                if not plan.verdict.is_closed:
                    return updated
                return plan.replacement
        return updated


def _class_ref(cls: type) -> cst.BaseExpression:
    return cst.Name(cls.__name__)


def build_direct_call(
    obj_name: str,
    impl_class: type,
    method_name: str,
    args: list[cst.Arg | cst.BaseExpression] | None = None,
) -> cst.Call:
    call_args = [cst.Arg(cst.Name(obj_name))]
    for arg in args or []:
        call_args.append(arg if isinstance(arg, cst.Arg) else cst.Arg(arg))
    return cst.Call(
        func=cst.Attribute(
            value=_class_ref(impl_class),
            attr=cst.Name(method_name),
        ),
        args=call_args,
    )


def build_isinstance_chain(
    obj_name: str,
    impl_map: dict[type, cst.BaseExpression],
    verdict: ClosureVerdict,
) -> cst.BaseExpression:
    items = list(impl_map.items())
    if not items:
        raise ValueError("impl_map is empty")
    if len(items) == 1:
        return items[0][1]

    last_cls, last_expr = items[-1]
    result: cst.BaseExpression = last_expr
    for cls, expr in reversed(items[:-1]):
        result = cst.IfExp(
            test=cst.Call(
                func=cst.Name("isinstance"),
                args=[
                    cst.Arg(cst.Name(obj_name)),
                    cst.Arg(_class_ref(cls)),
                ],
            ),
            body=expr,
            orelse=result,
        )
    return result
