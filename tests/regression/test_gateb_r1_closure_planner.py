"""Regression tests for the closure/planner R1 findings of the full Gate B review."""

import json
import textwrap

from flatten.cli import main
from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.finals import final
from flatten.planner import _most_conservative


def _trace_plan(tmp_path, capsys, name, source_text, closed_world=False):
    source = tmp_path / f"{name}.py"
    source.write_text(textwrap.dedent(source_text), encoding="utf-8")
    obs = tmp_path / f"{name}.json"
    plan = tmp_path / f"{name}.plan.json"
    assert main(["trace", source.as_posix(), "--entry", f"{name}:main",
                 "--out", obs.as_posix()]) == 0
    command = ["plan", source.as_posix(), "--observations", obs.as_posix(),
               "--out", plan.as_posix()]
    if closed_world:
        command.append("--closed-world")
    assert main(command) in (0, 2)
    capsys.readouterr()
    return json.loads(plan.read_text(encoding="utf-8"))


def test_conditionally_bound_receiver_is_not_pinned_to_the_observed_type(tmp_path, capsys):
    raw = _trace_plan(
        tmp_path,
        capsys,
        "condbind",
        """
        from flatten.finals import final


        @final
        class A:
            def run(self):
                return "A"


        class B:
            def run(self):
                return "B"


        def main(flag=True):
            w = A() if flag else B()
            return w.run()
        """,
    )
    assert raw["rewrite_plans"] == []


def test_rebound_receiver_is_not_pinned(tmp_path, capsys):
    raw = _trace_plan(
        tmp_path,
        capsys,
        "rebound",
        """
        from flatten.finals import final


        @final
        class A:
            def run(self):
                return "A"


        class B:
            def run(self):
                return "B"


        def main():
            w = A()
            w = B()
            return w.run()
        """,
    )
    assert raw["rewrite_plans"] == []


def test_single_constructor_binding_is_still_planned(tmp_path, capsys):
    raw = _trace_plan(
        tmp_path,
        capsys,
        "pinned_ok",
        """
        from flatten.finals import final


        @final
        class A:
            def run(self):
                return "A"


        def main():
            w = A()
            return w.run()
        """,
    )
    assert len(raw["rewrite_plans"]) == 1


def test_final_receiver_does_not_authorize_an_unrelated_class_in_any_order():
    @final
    class A:
        def run(self):
            return "a"

    class B:
        def run(self):
            return "b"

    for order in ([A, B], [B, A]):
        verdict = ClosureChecker().check("B.run", order)
        assert verdict.status is not ClosureStatus.CLOSED, order


def test_observed_override_of_a_final_method_is_not_closed():
    class Base:
        @final
        def run(self):
            return "base"

    class Child(Base):
        def run(self):  # type: ignore[override]
            return "child"

    assert ClosureChecker().check("Base.run", [Child]).status is not ClosureStatus.CLOSED


def test_sealed_descendant_does_not_authorize_its_root():
    class Root:
        def run(self):
            return "root"

    class Child(Root):
        def run(self):
            return "child"

    config = ClosureConfig(sealed_roots={f"{Child.__module__}.{Child.__qualname__}"})
    assert ClosureChecker(config).check("Root.run", [Child]).status is not ClosureStatus.CLOSED


def test_staticmethod_and_classmethod_bindings_are_unsafe():
    @final
    class WithStatic:
        @staticmethod
        def run():
            return 1

    @final
    class WithClassmethod:
        @classmethod
        def run(cls):
            return 1

    for cls in (WithStatic, WithClassmethod):
        verdict = ClosureChecker().check(f"{cls.__qualname__}.run", [cls])
        assert verdict.status is ClosureStatus.UNSAFE


def test_missing_method_is_not_closed():
    @final
    class Empty:
        pass

    assert ClosureChecker().check("Empty.run", [Empty]).status is not ClosureStatus.CLOSED


def test_metaclass_receiver_does_not_crash_the_checker():
    class Meta(type):
        def run(cls):
            return 1

    verdict = ClosureChecker().check("Meta.run", [Meta])
    assert verdict.status is not ClosureStatus.CLOSED


def test_dynamic_import_via_import_module_is_unsafe():
    import importlib

    @final
    class Loader:
        def run(self):
            return importlib.import_module("math").sqrt(4)

    assert ClosureChecker().check("Loader.run", [Loader]).status is ClosureStatus.UNSAFE


def test_verdict_collision_keeps_the_verdict_with_blockers_in_either_order():
    clean = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[],
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        evidence=("e",),
    )
    blocked = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[],
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        evidence=("e",),
        blockers=("observed unsafe binding",),
    )
    assert _most_conservative(clean, blocked).blockers
    assert _most_conservative(blocked, clean).blockers


def test_closed_world_notices_sibling_module_subclasses(tmp_path, capsys):
    (tmp_path / "sibling.py").write_text(
        "from app import Base\n\n\nclass Hidden(Base):\n    def run(self):\n"
        "        return 'hidden'\n",
        encoding="utf-8",
    )
    raw = _trace_plan(
        tmp_path,
        capsys,
        "app",
        """
        class Base:
            def run(self):
                return "base"


        def main():
            w = Base()
            return w.run()
        """,
        closed_world=True,
    )
    assert raw["rewrite_plans"] == []
    assert any("closed-world scan" in " ".join(v["blockers"]) for v in raw["verdicts"])


def test_dispatch_transformer_changes_only_the_planned_call_node():
    import libcst as cst

    from flatten.contracts import TransformPlan
    from flatten.dispatch import DispatchTransformer

    source = "def f(w, v):\n    x = w.run()\n    y = w.run()\n    return x, y\n"
    module = cst.parse_module(source)
    calls = []

    class Collect(cst.CSTVisitor):
        def visit_Call(self, node):
            calls.append(node)

    module.visit(Collect())
    verdict = ClosureVerdict(
        "A.run", True, [], [], "CLOSED", status=ClosureStatus.CLOSED, evidence=("e",)
    )
    plan = TransformPlan(calls[0], cst.parse_expression("A.run(w)"), verdict)

    code = module.visit(DispatchTransformer([plan])).code

    assert code.count("A.run(w)") == 1
    assert code.count("w.run()") == 1


def test_dispatch_transformer_ignores_plans_with_blockers():
    import libcst as cst

    from flatten.contracts import TransformPlan
    from flatten.dispatch import DispatchTransformer

    module = cst.parse_module("def f(w):\n    return w.run()\n")
    calls = []

    class Collect(cst.CSTVisitor):
        def visit_Call(self, node):
            calls.append(node)

    module.visit(Collect())
    call = calls[0]
    verdict = ClosureVerdict(
        "A.run",
        True,
        [],
        [],
        "CLOSED",
        status=ClosureStatus.CLOSED,
        evidence=("e",),
        blockers=("blocked",),
    )
    plan = TransformPlan(call, cst.parse_expression("A.run(w)"), verdict)

    assert "w.run()" in module.visit(DispatchTransformer([plan])).code
