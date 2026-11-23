"""Regression tests: a saved plan file must not authorize edits it was not generated for."""

import json
import textwrap

from flatten._cli_orchestration import _plan_digest
from flatten.cli import main

SOURCE = textwrap.dedent(
    """
    from flatten.finals import final


    @final
    class Worker:
        def run(self):
            return "worker"


    class Other:
        def run(self):
            return "other"


    def left():
        w = Worker()
        return w.run()


    def right():
        w = Other()
        return w.run()


    def main():
        return left()
    """
)


def _make_plan(tmp_path, capsys):
    source = tmp_path / "samesite.py"
    source.write_text(SOURCE, encoding="utf-8")
    obs = tmp_path / "obs.json"
    plan = tmp_path / "plan.json"
    assert main(["trace", source.as_posix(), "--entry", "samesite:main",
                 "--out", obs.as_posix()]) == 0
    assert main(["plan", source.as_posix(), "--observations", obs.as_posix(),
                 "--out", plan.as_posix()]) == 0
    capsys.readouterr()
    return source, plan, json.loads(plan.read_text(encoding="utf-8"))


def _rewrite(source, plan_path, out):
    return main(["rewrite", source.as_posix(), "--plan", plan_path.as_posix(),
                 "--out", out.as_posix(), "--apply", "--skip-verify"])


def test_genuine_plan_still_applies(tmp_path, capsys):
    source, plan, raw = _make_plan(tmp_path, capsys)
    assert len(raw["rewrite_plans"]) == 1
    out = tmp_path / "out.py"

    assert _rewrite(source, plan, out) == 0
    text = out.read_text(encoding="utf-8")
    assert "Worker.run(w)" in text
    assert text.count("w.run()") == 1  # the unplanned `right()` call is untouched


def test_moved_target_range_is_rejected(tmp_path, capsys):
    source, plan, raw = _make_plan(tmp_path, capsys)
    item = raw["rewrite_plans"][0]
    lines = SOURCE.splitlines()
    right_line = next(i for i, text in enumerate(lines, start=1) if i > 20 and "w.run()" in text)
    item["target_range"] = f"{right_line}:11-{right_line}:18"
    plan.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "out.py"

    assert _rewrite(source, plan, out) == 1
    assert not out.exists()


def test_hand_edited_replacement_is_rejected(tmp_path, capsys):
    source, plan, raw = _make_plan(tmp_path, capsys)
    raw["rewrite_plans"][0]["replacement"] = "'changed'"
    plan.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "out.py"

    assert _rewrite(source, plan, out) == 1
    assert "modified after planning" in capsys.readouterr().err
    assert not out.exists()


def test_plan_item_without_an_allowed_decision_is_rejected(tmp_path, capsys):
    source, plan, raw = _make_plan(tmp_path, capsys)
    for decision in raw["rewrite_decisions"]:
        decision["allowed"] = False
        decision["status"] = "unsafe"
    raw["plan_digest"] = _plan_digest(raw)  # a forger can simply recompute the digest
    plan.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "out.py"

    assert _rewrite(source, plan, out) == 1
    assert "no allowed rewrite decision" in capsys.readouterr().err
    assert not out.exists()
