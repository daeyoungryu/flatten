"""Smoke test: import + basic function call."""

import json
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

import flatten
from flatten.cli import main
from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.report import AnalysisReport
from flatten.tracer import Tracer


def test_version():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert flatten.__version__ == project["version"]


def test_closure_verdict_status():
    v = ClosureVerdict("MyClass.method", False, [], ["OS1: external subclass"], "OPEN")
    assert v.status == ClosureStatus.OPEN


def test_analysis_report_json_schema():
    v = ClosureVerdict("MyClass.method", False, [], [], "OPEN")
    report = AnalysisReport([v], confidence=0.5)
    payload = json.loads(report.to_json())
    assert {"confidence", "verdicts", "metadata", "errors"} <= set(payload)
    assert payload["confidence"] == 0.5


def test_cli_analyze_returns_json(capsys):
    rc = main(["analyze", "--format", "json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "confidence" in out


def test_tracer_context_manager():
    tracer = Tracer()
    with tracer:
        pass
    assert isinstance(tracer.records, list)


def test_main_module_entry_point():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "flatten", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "flatten" in result.stdout.lower()
