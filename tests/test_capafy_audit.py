from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import capafy_audit
from scripts.capafy_audit_report import render_summary


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_static_audit_writes_only_to_isolated_directory_and_skips_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    scope = tmp_path / "app.py"
    scope.write_text("print('safe')\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        commands.append(tuple(str(part) for part in command))
        if command[0] == "git":
            return _completed("true\n" if "rev-parse" in command else "")
        if command[1:3] == ["-c", "import flatten"]:
            return _completed()
        return _completed('{"call_sites": [], "verdicts": []}\n')

    monkeypatch.setattr(capafy_audit.subprocess, "run", fake_run)
    monkeypatch.setattr(capafy_audit, "_timestamp", lambda: "20260813T120000Z")

    result = capafy_audit.run_audit(scope, repo=tmp_path)

    output_dir = tmp_path / ".capafy-audit" / "20260813T120000Z"
    assert result["output_dir"] == str(output_dir)
    assert (output_dir / "analyze.json").exists()
    assert not (output_dir / "observations.json").exists()
    assert not any("trace" in command for command in commands)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        ".capafy-audit",
        ".git",
        "app.py",
    ]


def test_orchestrator_source_has_no_write_flag_literal() -> None:
    source = Path(capafy_audit.__file__).read_text(encoding="utf-8")
    forbidden = "--" + "apply"
    assert forbidden not in source


def test_trace_requires_explicit_execution_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    scope = tmp_path / "app.py"
    scope.write_text("def main():\n    return 1\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        commands.append(tuple(str(part) for part in command))
        if command[0] == "git":
            return _completed("true\n" if "rev-parse" in command else "")
        if command[1:3] == ["-c", "import flatten"]:
            return _completed()
        if "analyze" in command:
            return _completed('{"call_sites": [], "verdicts": []}\n')
        if "report" in command:
            return _completed(
                '{"call_sites": [], "verdicts": [], "rewrite_plans": []}\n'
            )
        out_index = command.index("--out") + 1
        Path(command[out_index]).write_text("{}", encoding="utf-8")
        return _completed()

    monkeypatch.setattr(capafy_audit.subprocess, "run", fake_run)
    monkeypatch.setattr(capafy_audit, "_timestamp", lambda: "20260813T120001Z")

    capafy_audit.run_audit(
        scope,
        repo=tmp_path,
        entry="app:main",
        yes_execute_trace=True,
    )

    assert any("trace" in command for command in commands)
    assert any("plan" in command for command in commands)
    assert any("report" in command for command in commands)


def test_status_filter_ignores_audit_output_but_detects_source_changes() -> None:
    before = "?? .capafy-audit/old/\n M existing.py\n"
    audit_only = "?? .capafy-audit/new/\n M existing.py\n"
    changed = audit_only + " M mutated.py\n"

    assert capafy_audit.filtered_status(before) == capafy_audit.filtered_status(
        audit_only
    )
    assert capafy_audit.status_diff(before, changed)


def test_render_summary_consumes_plan_backed_report_schema(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    summary = tmp_path / "summary.md"
    report.write_text(
        json.dumps(
            {
                "call_sites": [
                    {"call_site_id": "pkg/a.py:10:4-10:12"},
                    {"call_site_id": "pkg/b.py:7:2-7:9"},
                ],
                "verdicts": [
                    {
                        "status": "closed",
                        "method_qualname": "A.run",
                        "open_signals": [],
                    },
                    {
                        "status": "unsafe",
                        "method_qualname": "B.run",
                        "blockers": ["UNSAFE: dynamic attribute lookup"],
                        "call_site_id": "pkg/b.py:7:2-7:9",
                    },
                ],
                "rewrite_plans": [
                    {
                        "call_site_id": "pkg/a.py:10:4-10:12",
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    render_summary(report, summary, git_warning="mutated.py appeared")

    text = summary.read_text(encoding="utf-8")
    assert text.startswith("# WARNING: Repository changed during audit")
    assert "Total call sites: 2" in text
    assert "CLOSED candidates: 1" in text
    assert "UNSAFE: 1" in text
    assert "pkg/b.py:7" in text
    assert "pkg/a.py:10" in text
    assert "reference only; not applied" in text
