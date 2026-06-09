"""데이터 분기 보존 변환 — LibCST 기반."""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper


class CollapseTransformer(cst.CSTTransformer):
    """조건 분기를 보존하면서 불필요한 중간 변수 할당을 인라인한다."""

    def __init__(self, inline_targets: set[str]) -> None:
        self._inline_targets = inline_targets
        self._bindings: dict[str, cst.BaseExpression] = {}

    def visit_Assign(self, node: cst.Assign) -> bool:
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                if target.target.value in self._inline_targets:
                    self._bindings[target.target.value] = node.value
        return True

    def leave_Name(self, original: cst.Name, updated: cst.Name) -> cst.BaseExpression:
        if updated.value in self._bindings:
            return self._bindings[updated.value]
        return updated


def collapse_source(source: str, inline_targets: set[str]) -> str:
    """소스 코드에서 지정된 변수 바인딩을 인라인한 새 소스를 반환한다."""
    tree = cst.parse_module(source)
    transformer = CollapseTransformer(inline_targets)
    new_tree = tree.visit(transformer)
    return new_tree.code
