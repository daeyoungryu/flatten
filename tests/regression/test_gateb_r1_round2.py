"""Round-2 regression tests (delta Gate B findings against the first R1 fix set)."""

import json
import os
import textwrap
from pathlib import Path

import libcst as cst
import pytest

from flatten._cli_orchestration import (
    _byte_column_to_char_column,
    _call_site_for_range,
    _reject_output_alias,
)
from flatten.benchmarks import write_benchmark_reports
from flatten.cli import main
from flatten.closure import ClosureChecker
from flatten.contracts import ClosureStatus, ClosureVerdict, TransformPlan
from flatten.finals import final
from flatten.harness import (
    assert_equivalent,
    assert_modules_equivalent_subprocess,
    capture_behavior,
)
from flatten.planner import RewritePlanner


def test_verified_rewrite_loads_the_candidate_under_the_published_basename(tmp_path, capsys):
    source = tmp_path / "app.py"
    source.write_text(
        "from pathlib import Path\n\n\ndef main():\n    return Path(__file__).name == 'out.py'\n",
        encoding="utf-8",
    )
    obs = tmp_path / "obs.json"
    obs.write_text("[]", encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text("[{}]", encoding="utf-8")
    out = tmp_path / "out.py"

    code = main(["rewrite", source.as_posix(), "--observations", obs.as_posix(),
                 "--out", out.as_posix(), "--apply", "--entry", "app:main",
                 "--cases", cases.as_posix()])

    assert code == 1  # original returns False, the published module would return True
    assert not out.exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".flatten-stage")]


def test_staging_never_collides_with_existing_files(tmp_path):
    json_out = tmp_path / ".report.flatten-tmp"
    md_out = tmp_path / "report"
    write_benchmark_reports({"status": "x"}, out_json=json_out, out_md=md_out)
    assert json_out.exists() and md_out.exists()
    assert json.loads(json_out.read_text(encoding="utf-8")) == {"status": "x"}


def test_byte_columns_use_the_text_that_was_traced_not_a_stale_line_cache(tmp_path):
    path = tmp_path / "edited.py"
    path.write_text('x = ("가가가", a.run())\n', encoding="utf-8")
    stale = path.read_text(encoding="utf-8")
    prefix = 'x = ("가가가", '
    byte_col = len(prefix.encode("utf-8"))
    fresh_lines = ["x = (a.run(), b.run())", ""]
    assert (
        _byte_column_to_char_column(path.as_posix(), 1, byte_col, fresh_lines) == byte_col
    )
    assert _byte_column_to_char_column(path.as_posix(), 1, byte_col, stale.split("\n")) == len(
        prefix
    )


def test_assert_equivalent_runs_the_original_on_the_callers_objects():
    anchor: list = []
    with pytest.raises(AssertionError):
        assert_equivalent(lambda x: x is anchor, lambda x: False, [((anchor,), {})])


def test_uncopyable_input_is_rejected_instead_of_shared():
    def reads(gen):
        return next(gen)

    with pytest.raises(ValueError):
        assert_equivalent(reads, reads, [(((i for i in range(2)),), {})])


def test_systemexit_code_type_is_part_of_the_observation():
    def zero():
        raise SystemExit(0)

    def text():
        raise SystemExit("0")

    with pytest.raises(AssertionError):
        assert_equivalent(zero, text, [((), {})])


def test_capture_behavior_still_accepts_func_as_keyword():
    assert capture_behavior(func=lambda: 1).value == 1


def test_final_leaf_does_not_close_its_non_final_root():
    class Base:
        def run(self):
            return "base"

    @final
    class Leaf(Base):
        def run(self):
            return "leaf"

    assert ClosureChecker().check("Base.run", [Leaf]).status is not ClosureStatus.CLOSED


def test_plan_file_without_digest_is_rejected(tmp_path, capsys):
    from tests.regression.test_gateb_r1_plan_file import _make_plan, _rewrite

    source, plan, raw = _make_plan(tmp_path, capsys)
    raw.pop("plan_digest")
    raw["rewrite_plans"][0]["replacement"] = "'edited'"
    plan.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "out.py"

    assert _rewrite(source, plan, out) == 1
    assert not out.exists()


def test_call_site_lookup_survives_windows_drive_letters():
    source = "def f(w):\n    return w.run()\n"
    site_id = "C:/proj/m.py:2:11-2:18"
    with pytest.raises(ValueError):
        _call_site_for_range(source, site_id, "2:0-2:5")
    assert _call_site_for_range(source, site_id, "2:11-2:18").call_site_id == site_id


def test_rewrite_source_refuses_a_closed_verdict_without_evidence():
    verdict = ClosureVerdict("A.run", True, [], [], "CLOSED", status=ClosureStatus.CLOSED)
    plan = TransformPlan(
        cst.parse_expression("w.run()"), cst.Integer("1"), verdict, target_range="2:11-2:18"
    )
    with pytest.raises(ValueError):
        RewritePlanner(opt_in=True).rewrite_source("def f(w):\n    return w.run()\n", [plan])


def test_subprocess_comparison_rejects_zero_cases(tmp_path):
    module = tmp_path / "m.py"
    module.write_text("def main():\n    return 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        assert_modules_equivalent_subprocess(module, module, "main", cases=[])


def test_hard_link_output_is_refused(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("x = 1\n", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        os.link(source, link)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(ValueError):
        _reject_output_alias(link, source)


def _trace_and_plan(tmp_path, capsys, name, text, extra_files=None, closed_world=False):
    for file_name, body in (extra_files or {}).items():
        (tmp_path / file_name).write_text(body, encoding="utf-8")
    source = tmp_path / f"{name}.py"
    source.write_text(textwrap.dedent(text), encoding="utf-8")
    obs = tmp_path / f"{name}.json"
    plan = tmp_path / f"{name}.plan.json"
    assert main(["trace", source.as_posix(), "--entry", f"{name}:main",
                 "--out", obs.as_posix()]) == 0
    command = ["plan", source.as_posix(), "--observations", obs.as_posix(),
               "--out", plan.as_posix()]
    if closed_world:
        command.append("--closed-world")
    main(command)
    capsys.readouterr()
    return json.loads(plan.read_text(encoding="utf-8"))


def test_closed_world_follows_import_aliases_in_sibling_modules(tmp_path, capsys):
    raw = _trace_and_plan(
        tmp_path,
        capsys,
        "aliasapp",
        """
        class Base:
            def run(self):
                return "base"


        def main():
            w = Base()
            return w.run()
        """,
        extra_files={
            "sibling.py": "from aliasapp import Base as Parent\n\n\n"
            "class Child(Parent):\n    def run(self):\n        return 'child'\n"
        },
        closed_world=True,
    )
    assert raw["rewrite_plans"] == []


def test_match_pattern_binding_prevents_receiver_pinning(tmp_path, capsys):
    raw = _trace_and_plan(
        tmp_path,
        capsys,
        "matchapp",
        """
        from flatten.finals import final


        @final
        class A:
            def run(self):
                return "A"


        def main(xs=()):
            w = A()
            match xs:
                case (w,):
                    pass
            return w.run()
        """,
    )
    assert raw["rewrite_plans"] == []


def test_path_alias_check_uses_real_paths(tmp_path):
    target = tmp_path / "a.py"
    target.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        _reject_output_alias(Path(tmp_path / "." / "a.py"), target)


def test_receiver_pinning_check_does_not_need_match_ast_nodes(monkeypatch):
    import flatten.planner as planner_module
    from flatten.discovery import discover_call_sites

    monkeypatch.setattr(planner_module, "_MATCH_CAPTURE_NODES", ())
    monkeypatch.setattr(planner_module, "_MATCH_MAPPING_NODES", ())
    source = (
        "class A:\n    def run(self):\n        return 1\n\n\n"
        "def f():\n    w = A()\n    return w.run()\n"
    )
    site = discover_call_sites(source, filename="/virtual/x.py")[0]

    assert planner_module._is_receiver_pinned_by_constructor(source, site, ["x.A"]) is True


def test_behavior_hash_accepts_a_target_keyword_named_func():
    from flatten.harness import compute_behavior_hash

    def target(*, func):
        return func

    assert compute_behavior_hash(target, [((), {"func": 1})])


def test_systemexit_observation_includes_the_message_text():
    class Code:
        def __repr__(self):
            return "0"

        def __str__(self):
            return "failed"

    def zero():
        raise SystemExit(0)

    def odd():
        raise SystemExit(Code())

    with pytest.raises(AssertionError):
        assert_equivalent(zero, odd, [((), {})])


def test_rewrite_refuses_a_hard_link_to_its_own_input(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def main():\n    return 1\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        os.link(source, link)
    except OSError:
        pytest.skip("hard links unavailable")
    obs = tmp_path / "obs.json"
    obs.write_text("[]", encoding="utf-8")

    code = main(["rewrite", source.as_posix(), "--observations", obs.as_posix(),
                 "--out", link.as_posix(), "--apply", "--skip-verify"])

    assert code == 1
    assert source.read_text(encoding="utf-8") == "def main():\n    return 1\n"
