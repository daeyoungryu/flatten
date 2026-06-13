import json
import subprocess
import sys

import pytest

from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.discovery import discover_call_sites
from flatten.harness import assert_equivalent
from flatten.observations import ObservationRecord, observations_from_json
from flatten.planner import RewritePlanner
from flatten.transformer import rewrite_source_with_plan


def test_discovery_uses_position_based_ids_for_identical_calls():
    source = (
        "def f(a, b):\n"
        "    x = a.run(1)\n"
        "    y = a.run(1)\n"
        "    z = b.run(1)\n"
        "    return x, y, z\n"
    )

    sites = discover_call_sites(source, filename="sample.py")

    run_sites = [site for site in sites if site.method_name == "run"]
    assert len(run_sites) == 3
    assert len({site.call_site_id for site in run_sites}) == 3
    assert [site.receiver_expr for site in run_sites] == ["a", "a", "b"]
    assert run_sites[0].line == 2
    assert run_sites[1].line == 3
    assert run_sites[2].line == 4


def test_closure_closes_final_local_hierarchy_and_rejects_adversarial_cases():
    from flatten.finals import final

    @final
    class Only:
        def run(self, value):
            return value + 1

    closed = ClosureChecker(ClosureConfig(allow_final=True)).check("Only.run", [Only])

    assert closed.is_closed is True
    assert closed.signal == "CLOSED"

    class Base:
        def run(self):
            return "base"

    class Child(Base):
        def run(self):
            return "child"

    class Unobserved(Base):
        def run(self):
            return "missing"

    open_verdict = ClosureChecker().check("Base.run", [Child])
    assert open_verdict.is_closed is False
    assert open_verdict.signal == "OPEN"
    assert any("unobserved subclasses" in signal for signal in open_verdict.open_signals)

    Base.run = lambda self: "patched"
    unsafe = ClosureChecker().check("Base.run", [Base, Child, Unobserved])
    assert unsafe.signal == "UNSAFE"
    assert any("monkey patch" in signal for signal in unsafe.open_signals)

    class Dynamic:
        def __getattribute__(self, name):
            return super().__getattribute__(name)

        def run(self):
            return "dynamic"

    dynamic = ClosureChecker().check("Dynamic.run", [Dynamic])
    assert dynamic.signal == "UNSAFE"
    assert any("__getattribute__" in signal for signal in dynamic.open_signals)

    class Left:
        def run(self):
            return "left"

    class Right:
        def run(self):
            return "right"

    class Diamond(Left, Right):
        pass

    multiple = ClosureChecker().check("Left.run", [Diamond])
    assert multiple.signal == "UNSAFE"
    assert any("multiple inheritance" in signal for signal in multiple.open_signals)

    class WithProperty:
        @property
        def run(self):
            return lambda: "property"

    descriptor = ClosureChecker().check("WithProperty.run", [WithProperty])
    assert descriptor.signal == "UNSAFE"
    assert any("descriptor/property" in signal for signal in descriptor.open_signals)


def test_closure_marks_external_module_boundary_open():
    class ExternalBase:
        def run(self):
            return "external"

    ExternalBase.__module__ = "outside.plugin"

    verdict = ClosureChecker(
        ClosureConfig(package_prefixes=("inside_app",), closed_world=True)
    ).check("ExternalBase.run", [ExternalBase])

    assert verdict.signal == "OPEN"
    assert any("external module boundary" in signal for signal in verdict.open_signals)


def test_harness_compares_stderr_and_exception_messages():
    def left():
        print("same", file=sys.stderr)
        raise ValueError("same")

    def right():
        print("same", file=sys.stderr)
        raise ValueError("same")

    assert_equivalent(left, right, [((), {})])

    def different_stderr():
        print("different", file=sys.stderr)
        raise ValueError("same")

    with pytest.raises(AssertionError, match="stderr"):
        assert_equivalent(left, different_stderr, [((), {})])


def test_planner_and_transformer_rewrite_exact_site_with_guarded_dispatch():
    source = (
        "class A:\n"
        "    def run(self, value):\n"
        "        return value + 1\n"
        "class B:\n"
        "    def run(self, value):\n"
        "        return value + 2\n"
        "def f(a, b):\n"
        "    x = a.run(1)\n"
        "    y = a.run(1)\n"
        "    return x, y, b.run(1)\n"
    )
    sites = discover_call_sites(source, filename="sample.py")
    target = [site for site in sites if site.line == 9][0]
    observations = [
        ObservationRecord(
            call_site_id=target.call_site_id,
            receiver_type="sample.A",
            resolved_function="sample.A.run",
            module="sample",
            qualname="A.run",
        ),
        ObservationRecord(
            call_site_id=target.call_site_id,
            receiver_type="sample.B",
            resolved_function="sample.B.run",
            module="sample",
            qualname="B.run",
        ),
    ]
    verdict = ClosureVerdict(
        "A.run",
        True,
        [],
        signal="CLOSED",
        rationale="test closed fixture",
        status=ClosureStatus.CLOSED,
        evidence=("test closed fixture",),
    )

    plans = RewritePlanner(opt_in=True).plan_from_observations(
        source,
        sites,
        observations,
        [verdict],
    )
    rewritten = rewrite_source_with_plan(source, plans)

    assert len(plans) == 1
    assert plans[0].target_call_site.call_site_id == target.call_site_id
    assert "x = a.run(1)" in rewritten
    assert (
        "A.run(a, 1) if isinstance(a, A) else "
        "B.run(a, 1) if isinstance(a, B) else a.run(1)"
    ) in rewritten
    assert "return x, y, b.run(1)" in rewritten


def test_observation_json_schema_round_trips_call_site_linkage():
    payload = [
        {
            "call_site_id": "sample.py:2:11-2:19",
            "receiver_type": "sample.A",
            "resolved_function": "sample.A.run",
            "module": "sample",
            "qualname": "A.run",
        }
    ]

    records = observations_from_json(json.dumps(payload))

    assert records == [
        ObservationRecord(
            call_site_id="sample.py:2:11-2:19",
            receiver_type="sample.A",
            resolved_function="sample.A.run",
            module="sample",
            qualname="A.run",
        )
    ]


def test_cli_analyze_plan_rewrite_verify_integration(tmp_path):
    source = tmp_path / "simple.py"
    rewritten = tmp_path / "simple_rewritten.py"
    obs = tmp_path / "obs.json"
    cases = tmp_path / "cases.json"
    source.write_text(
        "from flatten.finals import final\n\n"
        "@final\n"
        "class Worker:\n"
        "    def run(self, value):\n"
        "        print('value', value)\n"
        "        return value + 1\n\n"
        "def main():\n"
        "    return Worker().run(2)\n",
        encoding="utf-8",
    )
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source}:10:11-10:26",
                    "receiver_type": "simple.Worker",
                    "resolved_function": "simple.Worker.run",
                    "module": "simple",
                    "qualname": "Worker.run",
                }
            ]
        ),
        encoding="utf-8",
    )
    cases.write_text(json.dumps([{"args": [], "kwargs": {}}]), encoding="utf-8")

    analyze = subprocess.run(
        [sys.executable, "-m", "flatten", "analyze", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    plan = subprocess.run(
        [sys.executable, "-m", "flatten", "plan", str(source), "--observations", str(obs)],
        check=False,
        capture_output=True,
        text=True,
    )
    rewrite = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "rewrite",
            str(source),
            "--observations",
            str(obs),
            "--out",
            str(rewritten),
            "--apply",
            "--entry",
            "simple:main",
            "--cases",
            str(cases),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "verify",
            str(source),
            str(rewritten),
            "--entry",
            "simple:main",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert analyze.returncode == 0, analyze.stderr
    assert "call_sites" in analyze.stdout
    assert plan.returncode == 0, plan.stderr
    assert "rewrite_plans" in plan.stdout
    assert rewrite.returncode == 0, rewrite.stderr
    assert "Worker.run(Worker(), 2)" in rewritten.read_text(encoding="utf-8")
    assert verify.returncode == 0, verify.stderr
    assert "equivalent" in verify.stdout
