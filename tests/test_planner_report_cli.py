import json

import libcst as cst

from flatten.contracts import ClosureVerdict, TransformPlan
from flatten.planner import RewritePlanner
from flatten.report import AnalysisReport


def test_rewrite_planner_is_disabled_by_default():
    planner = RewritePlanner()
    verdict = ClosureVerdict("Obj.run", False, [], ["OPEN: observed only"], "OPEN")

    assert planner.plan(verdict, []) == []


def test_rewrite_planner_opt_in_adds_warning_to_rewritten_source():
    source = "def f(obj):\n    return obj.run()\n"
    verdict = ClosureVerdict("Obj.run", False, [], ["OPEN: observed only"], "OPEN")
    plan = TransformPlan(
        cst.parse_expression("obj.run()"),
        cst.Integer("1"),
        verdict,
        target_range="2:11-2:20",
    )

    rewritten = RewritePlanner(opt_in=True).rewrite_source(source, [plan])

    assert "observed-based guess; unobserved implementations may exist" in rewritten
    assert "return 1" in rewritten


def test_analysis_report_renders_json_and_html():
    verdict = ClosureVerdict("Obj.run", False, [], ["OPEN: observed only"], "OPEN")
    report = AnalysisReport([verdict], confidence=0.25)

    payload = json.loads(report.to_json())
    assert payload["confidence"] == 0.25
    assert payload["verdicts"][0]["method_qualname"] == "Obj.run"
    assert "<html" in report.to_html().lower()


def test_cli_analyze_smoke(capsys):
    from flatten.cli import main

    exit_code = main(["analyze", "--format", "json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["confidence"] == 0.0
