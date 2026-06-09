import libcst as cst

from flatten.contracts import ClosureVerdict
from flatten.dispatch import build_direct_call, build_isinstance_chain


class Single:
    def run(self, value):
        return value


class First:
    def run(self, value):
        return value


class Second:
    def run(self, value):
        return value


def _code(expr: cst.BaseExpression) -> str:
    return cst.Module([]).code_for_node(expr)


def test_build_direct_call_uses_impl_method():
    expr = build_direct_call("obj", Single, "run", [cst.Integer("3")])
    assert _code(expr) == "Single.run(obj, 3)"


def test_single_impl_chain_collapses_to_direct_call():
    verdict = ClosureVerdict("Base.run", True, [Single])
    expr = build_isinstance_chain(
        "obj",
        {Single: cst.Call(cst.Attribute(cst.Name("Single"), cst.Name("run")))},
        verdict,
    )
    assert _code(expr) == "Single.run()"


def test_multiple_impl_chain_uses_isinstance_pattern():
    verdict = ClosureVerdict("Base.run", True, [First, Second])
    expr = build_isinstance_chain(
        "obj",
        {
            First: cst.SimpleString("'first'"),
            Second: cst.SimpleString("'second'"),
        },
        verdict,
    )
    code = _code(expr)

    assert "isinstance(obj, First)" in code
    assert "'first' if" in code
    assert "else 'second'" in code
