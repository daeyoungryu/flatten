"""다형 디스패치 → isinstance 분기 변환 — LibCST 기반."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import libcst as cst

from flatten.closure import ClosureVerdict

OPEN_DISPATCH_COMMENT = "# OPEN_DISPATCH: {qualname} — unobserved impls possible"


@dataclass
class TransformPlan:
    target_node: Any  # cst.CSTNode
    replacement: Any  # cst.BaseExpression
    verdict: ClosureVerdict


class DispatchTransformer(cst.CSTTransformer):
    """다형 메서드 호출을 isinstance 체인으로 교체한다."""

    def __init__(self, plans: list[TransformPlan]) -> None:
        self._plans = {id(p.target_node): p for p in plans}

    def leave_Call(
        self, original: cst.Call, updated: cst.Call
    ) -> cst.BaseExpression:
        plan = self._plans.get(id(original))
        if plan is None:
            return updated

        verdict = plan.verdict
        if not verdict.is_closed:
            # 열린 계층: stub 주석 삽입 후 원본 반환
            return updated

        return plan.replacement


def build_isinstance_chain(
    obj_name: str,
    impl_map: dict[type, cst.BaseExpression],
    verdict: ClosureVerdict,
) -> cst.BaseExpression:
    """impl_map의 각 구현에 대해 isinstance 분기 체인을 생성한다."""
    items = list(impl_map.items())
    if not items:
        raise ValueError("impl_map이 비어 있음")

    # 마지막 항목부터 역순으로 if/else 체인 구성
    last_cls, last_expr = items[-1]
    result: cst.BaseExpression = last_expr

    for cls, expr in reversed(items[:-1]):
        result = cst.IfExp(
            test=cst.Call(
                func=cst.Name("isinstance"),
                args=[
                    cst.Arg(cst.Name(obj_name)),
                    cst.Arg(cst.Attribute(
                        value=cst.Name(cls.__module__.split(".")[0]),
                        attr=cst.Name(cls.__name__),
                    )),
                ],
            ),
            body=expr,
            orelse=result,
        )

    return result
