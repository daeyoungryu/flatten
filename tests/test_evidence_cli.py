import json

from flatten.cli import main


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
