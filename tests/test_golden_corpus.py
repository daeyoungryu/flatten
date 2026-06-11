import json
from pathlib import Path

from flatten.cli import main

GOLDEN_ROOT = Path(__file__).parent / "golden"


def _run_plan_for_case(source: Path, tmp_path: Path, capsys):
    observations = tmp_path / f"{source.stem}.observations.json"
    assert (
        main(
            [
                "trace",
                source.as_posix(),
                "--entry",
                f"{source.stem}:main",
                "--out",
                observations.as_posix(),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "plan",
                source.as_posix(),
                "--observations",
                observations.as_posix(),
            ]
        )
        == 0
    )
    return json.loads(capsys.readouterr().out)


def test_golden_safe_cases_match_expected_rewrite_counts(tmp_path, capsys):
    for expected_path in (GOLDEN_ROOT / "safe").glob("*.expected.json"):
        source = expected_path.with_suffix("").with_suffix(".py")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))

        payload = _run_plan_for_case(source, tmp_path, capsys)

        assert len(payload["rewrite_plans"]) == expected["safe_rewrites"], source
        assert payload["verdicts"][0]["status"] == expected["status"], source


def test_golden_unsafe_cases_never_rewrite_and_report_blocker(tmp_path, capsys):
    for expected_path in (GOLDEN_ROOT / "unsafe").glob("*.expected.json"):
        source = expected_path.with_suffix("").with_suffix(".py")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))

        payload = _run_plan_for_case(source, tmp_path, capsys)
        verdict = payload["verdicts"][0]

        assert payload["rewrite_plans"] == [], source
        assert expected["safe_rewrites"] == 0
        assert verdict["status"] == expected["status"], source
        assert expected["blocked_reason"] in json.dumps(verdict).lower()
