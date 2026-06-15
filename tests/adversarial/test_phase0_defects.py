import json
import textwrap

from flatten.cli import main


def _write_case(tmp_path, source: str):
    path = tmp_path / "case_mod.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def test_cli_refuses_monkey_patched_dispatch_pipeline(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        class Animal:
            def speak(self): return "generic"
        class Dog(Animal):
            def speak(self): return "woof"
        class Cat(Animal):
            def speak(self): return "meow"
        def hacked(self): return "HACKED"
        Dog.speak = hacked
        def main():
            return [a.speak() for a in [Dog(), Cat()]]
        """,
    )
    obs = tmp_path / "obs.json"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )
    capsys.readouterr()
    assert main(["plan", path.as_posix(), "--observations", obs.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["rewrite_plans"] == []
    assert payload["verdicts"][0]["signal"] == "UNSAFE"
    assert "monkey patch" in json.dumps(payload["verdicts"][0]).lower()
    assert "explicit sealed root allowlist" not in json.dumps(payload["verdicts"][0]).lower()


def test_rewrite_without_apply_never_writes_output(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        from flatten.finals import final
        @final
        class Dog:
            def speak(self): return "woof"
        def main():
            d = Dog()
            return d.speak()
        """,
    )
    obs = tmp_path / "obs.json"
    out = tmp_path / "rewritten.py"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )
    assert (
        main(
            [
                "rewrite",
                path.as_posix(),
                "--observations",
                obs.as_posix(),
                "--out",
                out.as_posix(),
            ]
        )
        == 0
    )

    assert not out.exists()
    assert "dry run" in capsys.readouterr().out.lower()


def test_rewrite_with_apply_writes_output(tmp_path):
    path = _write_case(
        tmp_path,
        """
        from flatten.finals import final
        @final
        class Dog:
            def speak(self): return "woof"
        def main():
            d = Dog()
            return d.speak()
        """,
    )
    obs = tmp_path / "obs.json"
    out = tmp_path / "rewritten.py"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )
    assert (
        main(
            [
                "rewrite",
                path.as_posix(),
                "--observations",
                obs.as_posix(),
                "--out",
                out.as_posix(),
                "--apply",
                "--skip-verify",
            ]
        )
        == 0
    )

    assert out.exists()


def test_rewrite_apply_requires_verify_unless_explicitly_skipped(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        from flatten.finals import final
        @final
        class Dog:
            def speak(self): return "woof"
        def main():
            d = Dog()
            return d.speak()
        """,
    )
    obs = tmp_path / "obs.json"
    out = tmp_path / "rewritten.py"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )

    assert (
        main(
            [
                "rewrite",
                path.as_posix(),
                "--observations",
                obs.as_posix(),
                "--out",
                out.as_posix(),
                "--apply",
            ]
        )
        == 1
    )

    assert not out.exists()
    assert "--entry" in capsys.readouterr().err


def test_trace_binds_callsites_by_runtime_line_not_method_order(tmp_path):
    path = _write_case(
        tmp_path,
        """
        class First:
            def run(self): return "first"
        class Second:
            def run(self): return "second"

        def later(obj):
            return obj.run()

        def earlier(obj):
            return obj.run()

        def main():
            later(Second())
            earlier(First())
        """,
    )
    obs = tmp_path / "obs.json"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )

    records = json.loads(obs.read_text(encoding="utf-8"))
    assert records[0]["call_site_id"].endswith(":8:11-8:20")
    assert records[1]["call_site_id"].endswith(":11:11-11:20")


def test_trace_binds_same_line_multiple_calls_by_runtime_column(tmp_path):
    path = _write_case(
        tmp_path,
        """
        class Left:
            def run(self): return 1
        class Right:
            def run(self): return 2

        def main():
            left = Left()
            right = Right()
            return left.run() + right.run()
        """,
    )
    obs = tmp_path / "obs.json"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )

    records = json.loads(obs.read_text(encoding="utf-8"))
    call_site_ids = [record["call_site_id"] for record in records]
    assert len(call_site_ids) == 2
    assert all(call_site_ids)
    assert len(set(call_site_ids)) == 2
    assert call_site_ids[0].endswith(":10:11-10:21")
    assert call_site_ids[1].endswith(":10:24-10:35")


def test_final_method_with_instance_attr_read_is_closed(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        from flatten.finals import final
        @final
        class Box:
            def __init__(self, n):
                self.n = n
            def value(self):
                return self.n
        def main():
            box = Box(3)
            return box.value()
        """,
    )
    obs = tmp_path / "obs.json"

    assert (
        main(["trace", path.as_posix(), "--entry", "case_mod:main", "--out", obs.as_posix()])
        == 0
    )
    capsys.readouterr()
    assert main(["plan", path.as_posix(), "--observations", obs.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["verdicts"][0]["signal"] == "CLOSED"
    assert len(payload["rewrite_plans"]) == 1


def test_untrusted_plan_file_is_refused_without_verdict_and_source_hash(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        def main():
            return "original".upper()
        """,
    )
    plan = tmp_path / "plan.json"
    out = tmp_path / "rewritten.py"
    plan.write_text(
        json.dumps(
            {
                "rewrite_plans": [
                    {
                        "replacement": "'pwned'",
                        "target_range": "3:11-3:29",
                        "confidence": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "rewrite",
                path.as_posix(),
                "--plan",
                plan.as_posix(),
                "--out",
                out.as_posix(),
                "--apply",
            ]
        )
        == 1
    )
    assert not out.exists()
    assert "untrusted plan" in capsys.readouterr().err.lower()


def test_plan_file_rewrite_refuses_class_name_missing_from_source_scope(tmp_path, capsys):
    path = _write_case(
        tmp_path,
        """
        def main(obj):
            return obj.run()
        """,
    )
    plan = tmp_path / "plan.json"
    out = tmp_path / "rewritten.py"
    source = path.read_text(encoding="utf-8")
    import hashlib

    plan.write_text(
        json.dumps(
            {
                "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "rewrite_plans": [
                    {
                        "replacement": "External.run(obj)",
                        "target_range": "3:11-3:20",
                        "confidence": 1.0,
                        "verdict": {
                            "status": "closed",
                            "signal": "CLOSED",
                            "evidence": ["test closed fixture"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "rewrite",
                path.as_posix(),
                "--plan",
                plan.as_posix(),
                "--out",
                out.as_posix(),
                "--apply",
                "--skip-verify",
            ]
        )
        == 1
    )

    assert not out.exists()
    assert "not in source scope" in capsys.readouterr().err.lower()


def test_verify_uses_cases_file_and_reports_minimal_coverage(tmp_path, capsys):
    original = _write_case(
        tmp_path,
        """
        def main(x=0):
            return x + 1
        """,
    )
    rewritten = tmp_path / "rewritten.py"
    rewritten.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"args": [2], "kwargs": {}}]), encoding="utf-8")

    assert (
        main(
            [
                "verify",
                original.as_posix(),
                rewritten.as_posix(),
                "--entry",
                "case_mod:main",
                "--cases",
                cases.as_posix(),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["equivalent"] is True
    assert payload["verification_coverage"] == "minimal"
