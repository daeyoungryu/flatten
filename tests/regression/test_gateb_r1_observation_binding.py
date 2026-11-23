"""Regression tests for the observation-binding R1 findings of the full Gate B review."""

import json
import os
import re
import textwrap

from flatten._cli_orchestration import _byte_column_to_char_column, _observation_from_trace
from flatten._utils import normalize_filename
from flatten.cli import main
from flatten.contracts import OracleRecord
from flatten.discovery import discover_call_sites
from flatten.tracer import Tracer

HEADER = textwrap.dedent(
    """
    from types import MethodType

    from flatten.finals import final


    @final
    class A:
        def run(self):
            return "A"


    @final
    class B:
        def run(self):
            return "B"

    """
)


def _trace(tmp_path, capsys, name, body, entry="main"):
    source = tmp_path / f"{name}.py"
    source.write_text(HEADER + textwrap.dedent(body), encoding="utf-8")
    obs = tmp_path / f"{name}.json"
    code = main(["trace", source.as_posix(), "--entry", f"{name}:{entry}", "--out", obs.as_posix()])
    capsys.readouterr()
    assert code in (0, 2)
    return source, obs, json.loads(obs.read_text(encoding="utf-8"))


def _site_text(source, call_site_id):
    match = re.search(r":(\d+):(\d+)-\d+:\d+$", call_site_id)
    assert match, call_site_id
    line, start = int(match.group(1)), int(match.group(2))
    return source.read_text(encoding="utf-8").splitlines()[line - 1][start:]


def test_utf8_byte_columns_are_converted_to_character_columns(tmp_path, capsys):
    source, _, records = _trace(
        tmp_path,
        capsys,
        "utf8",
        """
        def main():
            a = A()
            b = B()
            return ("가가가가가가가가", a.run(), b.run())
        """,
    )
    by_impl = {r["qualname"]: r["call_site_id"] for r in records}
    assert _site_text(source, by_impl["A.run"]).startswith("a.run")
    assert _site_text(source, by_impl["B.run"]).startswith("b.run")


def test_byte_column_conversion_helper(tmp_path):
    path = tmp_path / "enc.py"
    path.write_text('x = "가" + a.run()\n', encoding="utf-8")
    prefix = 'x = "가" + '
    assert _byte_column_to_char_column(path.as_posix(), 1, len(prefix.encode("utf-8"))) == len(
        prefix
    )
    assert _byte_column_to_char_column(path.as_posix(), 1, -1) == -1


def test_single_same_name_candidate_must_contain_the_traced_column():
    source = "def f(a, b):\n    return b.run() if a else next(map(a.run, (0,)))\n"
    sites = discover_call_sites(source, filename="/virtual/sample.py")

    class Worker:
        def run(self):
            return 1

    record = OracleRecord(
        qualname=Worker.run.__qualname__,
        impl_class=Worker,
        args=(Worker(),),
        kwargs={},
        caller_filename="/virtual/sample.py",
        caller_lineno=2,
        caller_column=40,  # the map(...) call, not b.run()
    )
    assert _observation_from_trace(record, sites, 1).call_site_id == ""


def test_lambdas_on_one_line_get_distinct_positions():
    class W:
        def run(self):
            return 1

    a, b = W(), W()

    def main():
        return (lambda: a.run())(), (lambda: b.run())()

    with Tracer(target=main) as tracer:
        main()
    columns = [r.caller_column for r in tracer.records if r.qualname.endswith("W.run")]
    assert len(columns) == 2
    if -1 not in columns:
        assert columns[0] != columns[1]


def test_instance_level_override_is_not_recorded_as_the_class_method(tmp_path, capsys):
    _, _, records = _trace(
        tmp_path,
        capsys,
        "override",
        """
        class Alternate:
            def run(self):
                return "alternate"


        class C:
            def __init__(self):
                self.run = MethodType(Alternate.run, self)

            def run(self):
                return "C"


        def main():
            c = C()
            return c.run()
        """,
    )
    assert all(r["call_site_id"] == "" for r in records)


def test_stale_observations_are_rejected(tmp_path, capsys):
    source, obs, _ = _trace(
        tmp_path,
        capsys,
        "stale",
        """
        def main():
            w = A()
            return w.run()
        """,
    )
    source.write_text(
        source.read_text(encoding="utf-8").replace("w = A()", "w = B()"), encoding="utf-8"
    )

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix()]) == 1
    assert "different version" in capsys.readouterr().err


def test_observation_with_unknown_site_id_is_unbound_and_fails_strict(tmp_path, capsys):
    source, obs, records = _trace(
        tmp_path,
        capsys,
        "unknown",
        """
        def main():
            w = A()
            return w.run()
        """,
    )
    for record in records:
        record["call_site_id"] = record["call_site_id"].rsplit(":", 2)[0] + ":99:0-99:5"
        record.pop("source_hash", None)
    obs.write_text(json.dumps(records), encoding="utf-8")

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix(), "--strict"]) == 2


def test_strict_plan_fails_when_any_observation_is_unbound(tmp_path, capsys):
    source, obs, records = _trace(
        tmp_path,
        capsys,
        "mixed",
        """
        def main():
            w = A()
            return w.run()
        """,
    )
    extra = dict(records[0], call_site_id="")
    obs.write_text(json.dumps(records + [extra]), encoding="utf-8")

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix(), "--strict"]) == 2


def test_relative_filenames_are_resolved_against_the_current_directory(tmp_path, monkeypatch):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    monkeypatch.chdir(first)
    one = normalize_filename("same.py")
    monkeypatch.chdir(second)
    two = normalize_filename("same.py")
    assert one != two
    assert os.path.basename(os.path.dirname(two)) == "two"
