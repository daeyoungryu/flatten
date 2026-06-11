import json

import pytest

import flatten.harness as harness


def _assert_modules_equivalent_subprocess(*args, **kwargs):
    assert hasattr(harness, "assert_modules_equivalent_subprocess")
    return harness.assert_modules_equivalent_subprocess(*args, **kwargs)


def test_subprocess_harness_compares_stdout_stderr_return_and_effects(tmp_path):
    original = tmp_path / "original.py"
    rewritten = tmp_path / "rewritten.py"
    for path in (original, rewritten):
        path.write_text(
            """
EFFECTS = []

def main(value=2):
    print(f"out:{value}")
    import sys
    print("err:ok", file=sys.stderr)
    EFFECTS.append(value)
    return value + 1
""".lstrip(),
            encoding="utf-8",
        )

    result = _assert_modules_equivalent_subprocess(
        original,
        rewritten,
        "main",
        cases=[{"args": [3], "kwargs": {}}],
        effect_expression="EFFECTS",
        timeout=5.0,
        seed=123,
    )

    assert result["equivalent"] is True
    assert result["cases"] == 1
    assert result["seed"] == 123


def test_subprocess_harness_reports_exception_message_divergence(tmp_path):
    original = tmp_path / "original.py"
    rewritten = tmp_path / "rewritten.py"
    original.write_text("def main():\n    raise ValueError('left')\n", encoding="utf-8")
    rewritten.write_text("def main():\n    raise ValueError('right')\n", encoding="utf-8")

    with pytest.raises(AssertionError, match="exception divergence"):
        _assert_modules_equivalent_subprocess(
            original,
            rewritten,
            "main",
            cases=[{"args": [], "kwargs": {}}],
            timeout=5.0,
        )


def test_subprocess_harness_uses_timeout(tmp_path):
    original = tmp_path / "original.py"
    rewritten = tmp_path / "rewritten.py"
    original.write_text("def main():\n    return 1\n", encoding="utf-8")
    rewritten.write_text(
        "def main():\n    while True:\n        pass\n",
        encoding="utf-8",
    )

    with pytest.raises(TimeoutError):
        _assert_modules_equivalent_subprocess(
            original,
            rewritten,
            "main",
            cases=[{"args": [], "kwargs": {}}],
            timeout=0.2,
        )


def test_safety_model_documents_observed_input_limit():
    payload = json.loads(json.dumps({"ok": True}))
    assert payload["ok"] is True
    content = __import__("pathlib").Path("docs/SAFETY_MODEL.md").read_text(encoding="utf-8")
    assert "observed inputs" in content
    assert "not proof" in content
