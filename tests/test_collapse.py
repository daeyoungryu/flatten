import libcst as cst

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
    module = cst.parse_module(source)
    target = _first_call(module, "run")
    verdict = ClosureVerdict("Item.run", True, [])
    plan = TransformPlan(target, cst.Integer("5"), verdict)

    result = collapse_source(source, [plan])

    assert "for item in items:" in result
    assert "if flag:" in result
    assert "else:" in result
    assert "total += 5" in result
    assert "total += item.skip()" in result
