from pathlib import Path

import libcst as cst
import pytest

from flatten.closure import ClosureChecker
from flatten.confidence import confidence_score
from flatten.contracts import ClosureVerdict, TransformPlan
from flatten.dispatch import DispatchTransformer
from flatten.planner import REWRITE_WARNING, RewritePlanner
from flatten.tracer import Tracer, _snapshot_value


def test_confidence_score_bounds():
    assert confidence_score(ClosureVerdict("x", False, [], ["OPEN"], "OPEN")) == 0.0
    score = confidence_score(ClosureVerdict("x", False, [object], ["OPEN"], "OPEN"))
    assert 0.0 < score < 1.0


def test_dispatch_transformer_respects_open_verdict_and_closed_replacement():
    source = "def f(obj):\n    return obj.run()\n"
    module = cst.parse_module(source)
    target: cst.Call | None = None

    class Finder(cst.CSTVisitor):
        def visit_Call(self, node: cst.Call) -> None:
            nonlocal target
            target = node

    module.visit(Finder())
    assert target is not None
    open_plan = TransformPlan(target, cst.Integer("1"), ClosureVerdict("x", False, [], []))
    closed_plan = TransformPlan(target, cst.Integer("2"), ClosureVerdict("x", True, [], []))

    assert "obj.run()" in module.visit(DispatchTransformer([open_plan])).code
    assert "return 2" in module.visit(DispatchTransformer([closed_plan])).code


def test_planner_disabled_rewrite_raises_and_warning_is_not_duplicated():
    planner = RewritePlanner()
    with pytest.raises(ValueError, match="disabled"):
        planner.rewrite_source("def f():\n    return 1\n", [])

    source = f"{REWRITE_WARNING}\ndef f():\n    return 1\n"
    assert RewritePlanner(opt_in=True).rewrite_source(source, []) == source


def test_cli_html_smoke(capsys):
    from flatten.cli import main

    assert main(["analyze", "--format", "html"]) == 0
    assert "<html" in capsys.readouterr().out.lower()


def test_closure_handles_staticmethod_and_classmethod():
    class Example:
        @staticmethod
        def static(value):
            return value

        @classmethod
        def klass(cls, value):
            return value

    assert ClosureChecker().check("Example.static", [Example]).known_impls == [Example]
    assert ClosureChecker().check("Example.klass", [Example]).known_impls == [Example]


def test_tracer_fallback_backend_and_callback_no_frame(monkeypatch):
    calls = []
    monkeypatch.setattr("flatten.tracer._USE_MONITORING", False)
    monkeypatch.setattr("flatten.tracer.sys.settrace", lambda handler: calls.append(handler))

    tracer = Tracer()
    tracer.start()
    tracer._on_py_start((lambda: None).__code__, 0)
    tracer._on_py_return((lambda: None).__code__, 0, None)
    tracer.stop()

    assert len(calls) == 2


def test_snapshot_value_repr_fallback():
    class BadCopy:
        def __deepcopy__(self, memo):
            raise TypeError("no copy")

        def __repr__(self):
            return "BadCopy()"

    assert _snapshot_value(BadCopy()) == "BadCopy()"


def test_phase3_documentation_artifacts_exist_and_cover_claims():
    golden = Path("docs/golden_corpus.md").read_text(encoding="utf-8")
    claim_map = Path("docs/claim_test_map.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    for expected in [
        "simple_closed_single.py",
        "open_unobserved_subclass.py",
        "unsafe_monkey_patch.py",
        "unsafe_getattribute.py",
        "unsafe_phase2_dynamic.py",
    ]:
        assert expected in golden
    for claim in ["CLOSED", "OPEN", "UNSAFE", "RewriteDecision", "verify --cases"]:
        assert claim in claim_map
    assert "RewriteDecision" in readme
    assert "__setattr__" in readme
    assert "dynamic imports" in readme


def test_ci_runs_required_quality_gates():
    commands = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -c \"import flatten\"" in commands
    assert "python -m pytest -q" in commands
    assert "--cov=flatten" in commands
    assert "--cov-fail-under=90" in commands
    assert "python -m ruff check ." in commands
    assert "python -m mypy ." in commands
