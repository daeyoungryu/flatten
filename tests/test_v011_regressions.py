import json
import subprocess
import sys
from pathlib import Path

import libcst as cst

import flatten
from flatten.cli import _observation_from_trace
from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import ClosureStatus, ClosureVerdict, OracleRecord, TransformPlan
from flatten.discovery import discover_call_sites
from flatten.finals import final
from flatten.harness import _jsonable
from flatten.observations import ObservationRecord, TypeRef
from flatten.planner import RewritePlanner, _replacement_for_site
from flatten.tracer import Tracer


def test_v011_version_metadata_is_consistent():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert flatten.__version__ == "0.1.1"
    assert 'version = "0.1.1"' in pyproject


def test_flatten_polymorph_module_help_matches_flatten_help():
    flatten = subprocess.run(
        [sys.executable, "-m", "flatten", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    shim = subprocess.run(
        [sys.executable, "-m", "flatten_polymorph", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert flatten.returncode == 0
    assert shim.returncode == 0
    assert flatten.stdout == shim.stdout


def test_release_gate_script_and_ci_job_cover_built_wheel_contract():
    script = Path("scripts/release_gate.ps1")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    for expected in [
        "python -m build",
        "python -m compileall",
        "python -m flatten --help",
        "python -m flatten_polymorph --help",
        "python -m mypy --strict",
        "analyze",
        "trace",
        "plan",
        "rewrite",
        "verify",
    ]:
        assert expected in content

    assert "release-gate:" in workflow
    assert "scripts/release_gate.ps1" in workflow


def test_single_file_static_analysis_does_not_close_public_hierarchy(tmp_path):
    sample = tmp_path / "shapes.py"
    sample.write_text(
        """
class Shape:
    def area(self):
        raise NotImplementedError

class Circle(Shape):
    def area(self):
        return 3.14

class Square(Shape):
    def area(self):
        return 4.0

def entry():
    return Circle().area() + Square().area()
""".lstrip(),
        encoding="utf-8",
    )
    obs = tmp_path / "obs.json"

    trace = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "trace",
            "shapes.py",
            "--entry",
            "shapes:entry",
            "--out",
            str(obs),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert trace.returncode == 0, trace.stderr

    plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "plan",
            "shapes.py",
            "--observations",
            str(obs),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)

    statuses = {item["status"] for item in payload["verdicts"]}
    assert ClosureStatus.CLOSED.value not in statuses
    assert payload["rewrite_plans"] == []


def test_guarded_rewrite_falls_back_to_original_dynamic_dispatch_for_unmatched_type():
    source = """
class Shape:
    def area(self):
        raise NotImplementedError

class Circle(Shape):
    def area(self):
        return self.radius

class Square(Shape):
    def area(self):
        return self.side

class Triangle(Shape):
    def area(self):
        return self.height

def entry(shape):
    return shape.area()
""".lstrip()
    site = discover_call_sites(source, filename="sample.py")[0]
    replacement = _replacement_for_site(
        source,
        site,
        ["sample.Square", "sample.Circle"],
    )
    verdict = ClosureVerdict(
        "Shape.area",
        status=ClosureStatus.CLOSED,
        evidence=("test closed evidence",),
    )
    plan = TransformPlan(
        target_node=None,
        replacement=replacement,
        verdict=verdict,
        target_range=f"{site.line}:{site.column}-{site.end_line}:{site.end_column}",
        target_call_site=site,
        strategy="guarded",
    )
    rewritten = RewritePlanner(opt_in=True).rewrite_source(source, [plan])
    namespace: dict[str, object] = {}
    exec(rewritten, namespace)
    triangle = namespace["Triangle"]()
    triangle.height = 7

    assert namespace["entry"](triangle) == 7


def test_trace_binding_requires_matching_method_name_on_same_line():
    source = "def entry(a, b):\n    return a.foo() + b.bar()\n"
    sites = discover_call_sites(source, filename="sample.py")

    class Bar:
        def bar(self):
            return 2

    record = OracleRecord(
        qualname="Bar.bar",
        impl_class=Bar,
        args=(Bar(),),
        kwargs={},
        caller_filename=str(Path("sample.py").resolve()).replace("\\", "/"),
        caller_lineno=2,
        caller_column=11,
    )
    observation = _observation_from_trace(record, sites, 1)

    assert observation.method_name == "bar"
    assert observation.call_site_id == sites[1].call_site_id


def test_nested_call_trace_binds_inner_method(tmp_path):
    sample = tmp_path / "nested.py"
    sample.write_text(
        """
from flatten.finals import final

@final
class Item:
    def tag(self):
        return "x"

def entry():
    out = []
    it = Item()
    out.append(it.tag())
    return out
""".lstrip(),
        encoding="utf-8",
    )
    obs = tmp_path / "obs.json"

    trace = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "trace",
            "nested.py",
            "--entry",
            "nested:entry",
            "--out",
            str(obs),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert trace.returncode == 0, trace.stderr
    payload = json.loads(obs.read_text(encoding="utf-8"))
    tag_observations = [item for item in payload if item["method_name"] == "tag"]
    assert tag_observations
    assert all(item["call_site_id"] for item in tag_observations)


def test_planner_orders_subclasses_before_parents_in_guard_chain():
    source = """
class ZSquare:
    def area(self):
        return 4

class ASpecial(ZSquare):
    def area(self):
        return 9

def entry(shape):
    return shape.area()
""".lstrip()
    site = discover_call_sites(source, filename="sample.py")[0]
    verdict = ClosureVerdict(
        "ZSquare.area",
        known_impls=[ZSquare, ASpecial],
        status=ClosureStatus.CLOSED,
        evidence=("test closed evidence",),
    )
    observations = [
        ObservationRecord(
            call_site_id=site.call_site_id,
            receiver_type=TypeRef(__name__, "ZSquare", __file__, False),
            resolved_function=f"{__name__}.ZSquare.area",
            method_name="area",
        ),
        ObservationRecord(
            call_site_id=site.call_site_id,
            receiver_type=TypeRef(__name__, "ASpecial", __file__, False),
            resolved_function=f"{__name__}.ASpecial.area",
            method_name="area",
        ),
    ]

    plan = RewritePlanner(opt_in=True).plan_from_observations(
        source,
        [site],
        observations,
        [verdict],
    )[0]
    replacement = cst.Module([]).code_for_node(plan.replacement)

    assert replacement.index("isinstance(shape, ASpecial)") < replacement.index(
        "isinstance(shape, ZSquare)"
    )


class ZSquare:
    def area(self):
        return 4


class ASpecial(ZSquare):
    def area(self):
        return 9


def test_tracer_default_does_not_call_deepcopy_for_cli_minimal_capture():
    calls = 0

    class Noisy:
        def __deepcopy__(self, memo):
            nonlocal calls
            calls += 1
            return self

    @final
    class Worker:
        def run(self, payload):
            return payload

    with Tracer(capture_values=False) as tracer:
        Worker().run(Noisy())

    assert tracer.records
    assert calls == 0


def test_jsonable_handles_cycles_without_recursion_error():
    value: dict[str, object] = {}
    value["self"] = value

    assert _jsonable(value)["self"] == "<cycle>"


def test_closure_local_complete_is_probably_closed_not_allowed():
    @final
    class Leaf:
        def run(self):
            return 1

    verdict = ClosureChecker(
        ClosureConfig(allow_final=False, use_runtime_subclasses_for_closure=True)
    ).check("Leaf.run", [Leaf])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert verdict.status is ClosureStatus.PROBABLY_CLOSED
    assert decision.allowed is False
