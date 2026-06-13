import json

import libcst as cst
import pytest

from flatten.cli import _load_cases, main
from flatten.contracts import CallSite, ClosureStatus, ClosureVerdict, TransformPlan
from flatten.discovery import discover_call_sites
from flatten.planner import RewritePlanner, _replacement_for_site
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
    exit_code = main(["analyze", "--format", "json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["confidence"] == 0.0


def test_cli_analyze_html_and_file_output(tmp_path, capsys):
    source = tmp_path / "case.py"
    source.write_text("class A:\n    def run(self):\n        return 1\n", encoding="utf-8")

    exit_code = main(["analyze", source.as_posix(), "--format", "html"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "<html" in captured.out.lower()
    assert "Confidence: 0.00" in captured.out


def test_cli_plan_writes_json_output(tmp_path, capsys):
    source = tmp_path / "case.py"
    observations = tmp_path / "obs.json"
    out = tmp_path / "plan.json"
    source.write_text(
        "from flatten.finals import final\n\n"
        "@final\n"
        "class Worker:\n"
        "    def run(self):\n"
        "        return 1\n\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run()\n",
        encoding="utf-8",
    )
    observations.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source.as_posix()}:10:11-10:23",
                    "receiver_type": "case.Worker",
                    "resolved_function": "case.Worker.run",
                    "module": "case",
                    "qualname": "Worker.run",
                }
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan",
            source.as_posix(),
            "--observations",
            observations.as_posix(),
            "--out",
            out.as_posix(),
        ]
    )

    assert exit_code == 0
    assert out.exists()
    assert "wrote" in capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_hash"]
    assert payload["unbound_observations"] == 0


def test_cli_report_renders_verdict_signals(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "summary": "custom summary",
                "rewrite_plans": [{"strategy": "direct"}],
                "verdicts": [
                    {
                        "signal": "OPEN",
                        "rationale": "needs evidence",
                        "open_signals": ["unobserved subclass"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["report", plan.as_posix()]) == 0

    captured = capsys.readouterr()
    assert "custom summary" in captured.out
    assert "rewrite plans: 1" in captured.out
    assert "unobserved subclass" in captured.out


def test_load_cases_rejects_invalid_shapes(tmp_path):
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"args": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON list"):
        _load_cases(cases)

    cases.write_text(json.dumps([{"args": {}, "kwargs": {}}]), encoding="utf-8")
    with pytest.raises(ValueError, match="args must be list"):
        _load_cases(cases)

    cases.write_text(json.dumps([["not-enough"]]), encoding="utf-8")
    with pytest.raises(ValueError, match="case #0"):
        _load_cases(cases)


def test_plan_rejects_open_verdict_even_when_opted_in():
    verdict = ClosureVerdict("Obj.run", False, [], ["OPEN: observed only"], "OPEN")
    plan = TransformPlan(cst.Name("old"), cst.Name("new"), verdict)

    assert RewritePlanner(opt_in=True).plan(verdict, [plan]) == []


def test_plan_rejects_closed_verdict_when_not_opted_in():
    verdict = ClosureVerdict(
        "Obj.run",
        True,
        [],
        [],
        "CLOSED",
        status=ClosureStatus.CLOSED,
    )
    plan = TransformPlan(cst.Name("old"), cst.Name("new"), verdict)

    assert RewritePlanner(opt_in=False).plan(verdict, [plan]) == []


def test_replacement_for_site_uses_direct_strategy_for_one_receiver_type():
    source = "def f(obj):\n    return obj.run()\n"
    site = discover_call_sites(source, filename="case.py")[0]

    replacement = _replacement_for_site(source, site, ["pkg.mod.Worker"])

    assert cst.Module([]).code_for_node(replacement) == "Worker.run(obj)"


def test_replacement_for_site_uses_guard_for_two_receiver_types():
    source = "def f(obj):\n    return obj.run()\n"
    site = discover_call_sites(source, filename="case.py")[0]

    replacement = _replacement_for_site(source, site, ["pkg.mod.Base", "pkg.mod.Child"])

    assert cst.Module([]).code_for_node(replacement) == (
        "Base.run(obj) if isinstance(obj, Base) else "
        "Child.run(obj) if isinstance(obj, Child) else obj.run()"
    )


def test_replacement_for_site_uses_nested_guards_for_three_receiver_types():
    source = "def f(obj):\n    return obj.run()\n"
    site = discover_call_sites(source, filename="case.py")[0]

    replacement = _replacement_for_site(
        source,
        site,
        ["pkg.mod.Base", "pkg.mod.Child", "external.Leaf"],
    )

    assert cst.Module([]).code_for_node(replacement) == (
        "Base.run(obj) if isinstance(obj, Base) else "
        "Child.run(obj) if isinstance(obj, Child) else "
        "Leaf.run(obj) if isinstance(obj, Leaf) else obj.run()"
    )


def test_replacement_for_site_uses_receiver_override_in_call_and_guard():
    source = "def f(factory):\n    return factory().run()\n"
    site = CallSite(
        call_site_id="case.py:2:11-2:26",
        filename="case.py",
        line=2,
        column=11,
        end_line=2,
        end_column=26,
        qualified_name="factory().run",
        receiver_expr="factory()",
        method_name="run",
    )

    replacement = _replacement_for_site(
        source,
        site,
        ["pkg.mod.Base", "pkg.mod.Child"],
        receiver_override="_receiver",
    )

    assert cst.Module([]).code_for_node(replacement) == (
        "Base.run(_receiver) if isinstance(_receiver, Base) else "
        "Child.run(_receiver) if isinstance(_receiver, Child) else _receiver.run()"
    )
