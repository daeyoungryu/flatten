import json
import subprocess
import sys
import textwrap

from flatten.cli import main


def test_python_module_cli_help_exits_cleanly():
    result = subprocess.run(
        [sys.executable, "-m", "flatten", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_console_cli_json_schema_is_stable():
    result = subprocess.run(
        [sys.executable, "-m", "flatten", "analyze", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert {"confidence", "verdicts", "metadata", "errors"} <= set(payload)


def test_trace_cli_passes_entry_function_as_tracer_target(tmp_path, monkeypatch):
    source = tmp_path / "case_mod.py"
    source.write_text(
        textwrap.dedent(
            """
            def main():
                return "ok"
            """
        ),
        encoding="utf-8",
    )
    out = tmp_path / "obs.json"
    captured = {}

    class FakeTracer:
        def __init__(self, target=None, *, capture_values=False):
            captured["target"] = target
            captured["capture_values"] = capture_values
            self.records = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    monkeypatch.setattr("flatten._cli_orchestration.Tracer", FakeTracer)

    assert (
        main(["trace", source.as_posix(), "--entry", "case_mod:main", "--out", out.as_posix()])
        == 0
    )
    assert captured["target"] is not None
    assert captured["target"].__name__ == "main"
