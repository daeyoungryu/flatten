import libcst as cst
import pytest

from flatten.closure import ClosureChecker
from flatten.collapse import collapse_source
from flatten.contracts import ClosureVerdict, TransformPlan
from flatten.dispatch import build_direct_call, build_isinstance_chain
from flatten.harness import assert_equivalent
from flatten.tracer import Tracer, trace_calls
from tests.fixtures.diamond import A, B, C, D, E, make_all


def _first_call(module: cst.Module, method_name: str) -> cst.Call:
    calls: list[cst.Call] = []

    class Finder(cst.CSTVisitor):
        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute) and node.func.attr.value == method_name:
                calls.append(node)

    module.visit(Finder())
    return calls[0]


def _code(expr: cst.BaseExpression) -> str:
    return cst.Module([]).code_for_node(expr)


def test_a1_tracer_paths_create_same_oracle_record_shape():
    class Worker:
        def run(self, value):
            return value + 1

    worker = Worker()
    with trace_calls(worker.run) as tracer:
        worker.run(2)

    record = next(r for r in tracer.records if r.qualname.endswith("Worker.run"))
    assert set(record.__dataclass_fields__) == {
        "qualname",
        "impl_class",
        "args",
        "kwargs",
        "return_val",
        "call_site",
    }
    assert record.impl_class is Worker
    assert record.return_val == 3


def test_a2_detects_os1_through_os5_individually():
    checker = ClosureChecker()
    prefix = "x"

    class FreeVar:
        def run(self, value):
            return prefix + value

    def make_nonlocal():
        count = 0

        class NonlocalWrite:
            def run(self, value):
                nonlocal count
                count += 1
                return value

        return NonlocalWrite

    class InstanceAttr:
        def run(self, value):
            return self.factor + value

    class Base:
        def run(self, value):
            return value

    class Child(Base):
        pass

    class GrandChild(Child):
        pass

    checks = [
        ("OS1", checker.check("FreeVar.run", [FreeVar])),
        ("OS2", checker.check("FreeVar.run", [FreeVar])),
        ("OS3", checker.check("NonlocalWrite.run", [make_nonlocal()])),
        ("OS4", checker.check("InstanceAttr.run", [InstanceAttr])),
        ("OS5", checker.check("Base.run", [Base, Child])),
    ]
    assert all(
        any(signal.startswith(prefix) for signal in verdict.open_signals)
        for prefix, verdict in checks
    )


def test_a3_preserves_if_else_and_for_during_transform():
    source = (
        "def f(items, flag):\n"
        "    for item in items:\n"
        "        if flag:\n"
        "            item.run()\n"
        "        else:\n"
        "            item.skip()\n"
    )
    module = cst.parse_module(source)
    plan = TransformPlan(
        _first_call(module, "run"),
        build_direct_call("item", B, "process", [cst.Integer("1")]),
        ClosureVerdict("A.process", True, [B]),
    )
    result = collapse_source(source, [plan])
    assert "for item in items:" in result
    assert "if flag:" in result
    assert "else:" in result
    assert "B.process(item, 1)" in result


def test_a4_dispatch_single_and_multiple_impl_patterns():
    single = build_direct_call("obj", B, "process", [cst.Integer("4")])
    assert _code(single) == "B.process(obj, 4)"

    chain = build_isinstance_chain(
        "obj",
        {B: cst.SimpleString("'B'"), C: cst.SimpleString("'C'")},
        ClosureVerdict("A.process", True, [B, C]),
    )
    chain_code = _code(chain)
    assert "isinstance(obj, B)" in chain_code
    assert "else 'C'" in chain_code


def test_a5_equivalence_passes_and_divergence_is_detailed():
    assert_equivalent(lambda x: x + 1, lambda x: x + 1, [((1,), {})])
    with pytest.raises(AssertionError, match="input #0 return divergence"):
        assert_equivalent(lambda x: x + 1, lambda x: x + 2, [((1,), {})])


def test_a6_end_to_end_polymorphic_pipeline():
    objects = make_all()
    with trace_calls(A.process) as tracer:
        for obj in objects:
            obj.process(9)

    observed = {record.impl_class for record in tracer.records}
    verdict = ClosureChecker().check("A.process", [A, B, C, D, E])
    source = "def flattened(obj):\n    return obj.process(9)\n"
    module = cst.parse_module(source)
    target = _first_call(module, "process")
    replacement = build_isinstance_chain(
        "obj",
        {
            A: build_direct_call("obj", A, "process", [cst.Integer("9")]),
            B: build_direct_call("obj", B, "process", [cst.Integer("9")]),
            C: build_direct_call("obj", C, "process", [cst.Integer("9")]),
            D: build_direct_call("obj", D, "process", [cst.Integer("9")]),
            E: build_direct_call("obj", E, "process", [cst.Integer("9")]),
        },
        verdict,
    )
    result = collapse_source(source, [TransformPlan(target, replacement, verdict)])

    assert observed == {A, B, C, D, E}
    assert verdict.is_closed
    assert "isinstance(obj, A)" in result
    assert "E.process(obj, 9)" in result
