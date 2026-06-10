import libcst as cst
import pytest
from libcst.metadata import MetadataWrapper, PositionProvider

from flatten.collapse import CollapseTransformer, collapse_source
from flatten.contracts import ClosureVerdict, TransformPlan


def _first_call(module: cst.Module, name: str) -> cst.Call:
    calls: list[cst.Call] = []

    class Finder(cst.CSTVisitor):
        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute) and node.func.attr.value == name:
                calls.append(node)

    module.visit(Finder())
    return calls[0]


def _call_positions(source: str, name: str) -> list[tuple[cst.Call, str]]:
    wrapper = MetadataWrapper(cst.parse_module(source))
    positions: list[tuple[cst.Call, str]] = []

    class Finder(cst.CSTVisitor):
        METADATA_DEPENDENCIES = (PositionProvider,)

        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute) and node.func.attr.value == name:
                position = self.get_metadata(PositionProvider, node)
                positions.append(
                    (
                        node,
                        f"{position.start.line}:{position.start.column}-"
                        f"{position.end.line}:{position.end.column}",
                    )
                )

    wrapper.visit(Finder())
    return positions


def test_transform_plan_replaces_target_call_only():
    source = "def f(obj):\n    return obj.run(1) + obj.skip(2)\n"
    module = cst.parse_module(source)
    target = _first_call(module, "run")
    verdict = ClosureVerdict("Base.run", True, [])
    plan = TransformPlan(target, cst.Integer("10"), verdict, "single observed impl")

    result = module.visit(CollapseTransformer([plan])).code

    assert plan.rationale == "single observed impl"
    assert "return 10 + obj.skip(2)" in result


def test_collapse_source_preserves_if_else_and_for_structure():
    source = (
        "def f(items, flag):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        if flag:\n"
        "            total += item.run()\n"
        "        else:\n"
        "            total += item.skip()\n"
        "    return total\n"
    )
    calls = _call_positions(source, "run")
    verdict = ClosureVerdict("Item.run", True, [])
    plan = TransformPlan(calls[0][0], cst.Integer("5"), verdict, target_range=calls[0][1])

    result = collapse_source(source, [plan])

    assert "for item in items:" in result
    assert "if flag:" in result
    assert "else:" in result
    assert "total += 5" in result
    assert "total += item.skip()" in result


def test_plan_replaces_only_call_at_source_position_when_calls_are_identical():
    source = (
        "def f(obj):\n"
        "    first = obj.run()\n"
        "    second = obj.run()\n"
        "    return first, second\n"
    )
    calls = _call_positions(source, "run")
    verdict = ClosureVerdict("Obj.run", True, [])
    plan = TransformPlan(calls[0][0], cst.Integer("1"), verdict, target_range=calls[0][1])

    result = collapse_source(source, [plan])

    assert "first = 1" in result
    assert "second = obj.run()" in result


def test_set_inline_path_is_rejected_as_unsafe():
    with pytest.raises(ValueError, match="unsafe inline"):
        collapse_source("def f():\n    x = side_effect()\n    return x\n", {"x"})
