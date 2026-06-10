import json
import subprocess
import sys


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
