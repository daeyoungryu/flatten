import json

from flatten.cli import main
from flatten.evaluation import EvaluationCounts, compute_metrics
from flatten.report import evaluation_metrics_to_html


def test_evaluate_cli_reports_counts_for_source_file(tmp_path, capsys):
    source = tmp_path / "case.py"
    source.write_text(
        """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
""",
        encoding="utf-8",
    )

    assert main(["evaluate", source.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["total_call_sites"] == 1
    assert payload["counts"]["candidate_call_sites"] == 0
    assert payload["precision"] is None


def test_evaluate_cli_accepts_plan_file(tmp_path, capsys):
    source = tmp_path / "case.py"
    source.write_text(
        """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
""",
        encoding="utf-8",
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "rewrite_decisions": [
                    {
                        "method_qualname": "A.run",
                        "allowed": False,
                        "status": "unsafe",
                        "blockers": ["UNSAFE: monkey patch"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["evaluate", source.as_posix(), "--plan", plan.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["candidate_call_sites"] == 1
    assert payload["counts"]["unsafe_call_sites"] == 1


def test_evaluation_metrics_html_contains_review_fields():
    html = evaluation_metrics_to_html(
        compute_metrics(
            EvaluationCounts(
                total_call_sites=2,
                candidate_call_sites=1,
                rewritten_call_sites=1,
                rejected_call_sites=0,
                unsafe_call_sites=0,
                unknown_call_sites=0,
            ),
            [],
        )
    )

    assert "<html" in html
    assert "total_call_sites" in html
    assert "precision" in html
