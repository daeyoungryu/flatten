"""Regression tests for the verification/output-safety R1 findings of the full Gate B review."""

import json
import textwrap

import pytest

from flatten.benchmarks import write_benchmark_reports
from flatten.cli import main
from flatten.harness import assert_equivalent

PLANNABLE = textwrap.dedent(
    '''
    from flatten.finals import final


    @final
    class A:
        def run(self):
            return "A"


    def main(flag=True):
        w = A()
        return w.run()
    '''
)


def _plan_pinned(tmp_path, capsys):
    source = tmp_path / "pinned.py"
    source.write_text(PLANNABLE, encoding="utf-8")
    obs = tmp_path / "obs.json"
    args = ["trace", source.as_posix(), "--entry", "pinned:main", "--out", obs.as_posix()]
    assert main(args) == 0
    capsys.readouterr()
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"args": [False]}]), encoding="utf-8")
    return source, obs, cases


def _failing_verification(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("forced verification failure")

    monkeypatch.setattr("flatten._cli_orchestration.assert_equivalent", fail)


def test_assert_equivalent_rejects_zero_inputs():
    with pytest.raises(ValueError):
        assert_equivalent(lambda: 1, lambda: 2, [])


def test_cli_verify_rejects_empty_cases(tmp_path, capsys):
    one = tmp_path / "one.py"
    two = tmp_path / "two.py"
    one.write_text("def main():\n    return 1\n", encoding="utf-8")
    two.write_text("def main():\n    return 2\n", encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")

    code = main(["verify", one.as_posix(), two.as_posix(), "--entry", "m:main",
                 "--cases", cases.as_posix()])

    assert code == 1
    assert '"equivalent": true' not in capsys.readouterr().out


def test_systemexit_is_an_observed_outcome():
    def exits():
        raise SystemExit(0)

    with pytest.raises(AssertionError):
        assert_equivalent(exits, lambda: 7, [((), {})])


def test_mutable_inputs_are_not_shared_between_runs():
    def appends(items):
        items.append(1)
        return len(items)

    def reads(items):
        return len(items)

    with pytest.raises(AssertionError):
        assert_equivalent(appends, reads, [(([],), {})])


def test_default_return_comparison_distinguishes_types():
    with pytest.raises(AssertionError):
        assert_equivalent(lambda: 1, lambda: True, [((), {})])


def test_keyword_argument_named_effect_collectors_is_forwarded():
    def echo(*, effect_collectors):
        return effect_collectors

    assert_equivalent(echo, echo, [((), {"effect_collectors": 1})])


def test_rewrite_failure_keeps_existing_output(tmp_path, capsys, monkeypatch):
    source, obs, cases = _plan_pinned(tmp_path, capsys)
    _failing_verification(monkeypatch)
    out = tmp_path / "out.py"
    out.write_text("# KEEP\n", encoding="utf-8")

    code = main(["rewrite", source.as_posix(), "--observations", obs.as_posix(),
                 "--out", out.as_posix(), "--apply", "--entry", "pinned:main",
                 "--cases", cases.as_posix()])

    assert code == 1
    assert out.read_text(encoding="utf-8") == "# KEEP\n"
    assert not list(tmp_path.glob(".*flatten-tmp*"))


def test_rewrite_in_place_failure_keeps_source(tmp_path, capsys, monkeypatch):
    source, obs, cases = _plan_pinned(tmp_path, capsys)
    _failing_verification(monkeypatch)

    code = main(["rewrite", source.as_posix(), "--observations", obs.as_posix(),
                 "--out", source.as_posix(), "--apply", "--entry", "pinned:main",
                 "--cases", cases.as_posix()])

    assert code == 1
    assert source.read_text(encoding="utf-8") == PLANNABLE


def test_trace_and_plan_refuse_to_overwrite_their_source(tmp_path, capsys):
    source = tmp_path / "s.py"
    source.write_text(PLANNABLE, encoding="utf-8")

    assert main(["trace", source.as_posix(), "--entry", "s:main",
                 "--out", source.as_posix()]) == 1
    assert source.read_text(encoding="utf-8") == PLANNABLE
    capsys.readouterr()


def test_benchmark_rejects_catalog_as_output_and_same_output(tmp_path):
    catalog = tmp_path / "catalog.csv"
    header = "name,package,repo_url,category\n"
    catalog.write_text(header + "demo,demo,https://example.invalid/demo,lib\n", encoding="utf-8")
    original = catalog.read_text(encoding="utf-8")

    assert main(["benchmark", "--catalog", catalog.as_posix(),
                 "--out-json", catalog.as_posix()]) == 1
    assert catalog.read_text(encoding="utf-8") == original

    same = tmp_path / "same.out"
    assert main(["benchmark", "--catalog", catalog.as_posix(),
                 "--out-json", same.as_posix(), "--out-md", same.as_posix()]) == 1
    assert not same.exists()
    with pytest.raises(ValueError):
        write_benchmark_reports({}, out_json=same, out_md=same)


def test_specialize_does_not_embed_arguments_mutated_by_tracing(tmp_path):
    source = tmp_path / "sp.py"
    source.write_text(
        "def main(xs):\n    xs.append(1)\n    return len(xs)\n", encoding="utf-8"
    )
    args = tmp_path / "args.json"
    args.write_text("[[]]", encoding="utf-8")
    out = tmp_path / "out.py"

    code = main(["specialize", source.as_posix(), "--entry", "sp:main",
                 "--target", "sp:main", "--args-json", args.as_posix(), "--out", out.as_posix()])

    assert code == 0
    assert "main([])" in out.read_text(encoding="utf-8")


def test_specialize_keeps_non_bmp_strings_and_refuses_name_collision(tmp_path):
    source = tmp_path / "sp2.py"
    source.write_text("def main(s):\n    return len(s)\n", encoding="utf-8")
    args = tmp_path / "args.json"
    args.write_text(json.dumps(["\U0001F600"]), encoding="utf-8")
    out = tmp_path / "out2.py"
    code = main(["specialize", source.as_posix(), "--entry", "sp2:main",
                 "--target", "sp2:main", "--args-json", args.as_posix(), "--out", out.as_posix()])
    assert code == 0
    namespace: dict = {}
    exec(compile(out.read_text(encoding="utf-8"), "out2.py", "exec"), namespace)
    assert namespace["specialized"]() == 1

    clash = tmp_path / "sp3.py"
    clash.write_text("def specialized():\n    return 99\n\ndef main():\n    return 1\n",
                     encoding="utf-8")
    none_args = tmp_path / "none.json"
    none_args.write_text("[]", encoding="utf-8")
    clash_out = tmp_path / "o3.py"
    assert main(["specialize", clash.as_posix(), "--entry", "sp3:main", "--target", "sp3:main",
                 "--args-json", none_args.as_posix(), "--out", clash_out.as_posix()]) == 1


def test_loader_ignores_stale_bytecode(tmp_path):
    from flatten._cli_io import _load_module

    path = tmp_path / "stale.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")
    first = _load_module(path, "_gateb_stale_one")
    assert first.VALUE == 1
    stat = path.stat()
    path.write_text("VALUE = 2\n", encoding="utf-8")
    import os

    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert _load_module(path, "_gateb_stale_two").VALUE == 2
