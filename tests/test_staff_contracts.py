import json
import subprocess
import sys

from flatten.cli import main
from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef, observations_from_json
from flatten.planner import RewritePlanner


def test_observation_schema_uses_canonical_type_and_function_refs():
    payload = [
        {
            "call_site_id": "pkg/mod.py:10:8-10:18",
            "receiver_type": {
                "module": "pkg.mod",
                "qualname": "Worker",
                "file": "pkg/mod.py",
                "is_builtin": False,
            },
            "resolved_function": {
                "module": "pkg.mod",
                "qualname": "Worker.run",
                "file": "pkg/mod.py",
                "firstlineno": 3,
            },
            "method_name": "run",
            "frame_module": "pkg.mod",
            "order": 1,
            "input_hash": "case-1",
        }
    ]

    records = observations_from_json(json.dumps(payload))

    assert records == [
        ObservationRecord(
            call_site_id="pkg/mod.py:10:8-10:18",
            receiver_type=TypeRef("pkg.mod", "Worker", "pkg/mod.py", False),
            resolved_function=FunctionRef("pkg.mod", "Worker.run", "pkg/mod.py", 3),
            method_name="run",
            frame_module="pkg.mod",
            order=1,
            input_hash="case-1",
        )
    ]


def test_cli_plan_writes_plan_file_and_rewrite_consumes_plan(tmp_path):
    source = tmp_path / "case.py"
    obs = tmp_path / "obs.json"
    plan = tmp_path / "plan.json"
    rewritten = tmp_path / "rewritten.py"
    source.write_text(
        "from typing import final\n\n"
        "@final\n"
        "class Worker:\n"
        "    def run(self, value):\n"
        "        return value + 1\n\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run(2)\n",
        encoding="utf-8",
    )
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source}:10:11-10:24",
                    "receiver_type": {
                        "module": "case",
                        "qualname": "Worker",
                        "file": str(source),
                        "is_builtin": False,
                    },
                    "resolved_function": {
                        "module": "case",
                        "qualname": "Worker.run",
                        "file": str(source),
                        "firstlineno": 5,
                    },
                    "method_name": "run",
                    "frame_module": "case",
                    "order": 1,
                    "input_hash": "case-1",
                }
            ]
        ),
        encoding="utf-8",
    )

    plan_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "plan",
            str(source),
            "--observations",
            str(obs),
            "--out",
            str(plan),
            "--closed-world",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    rewrite_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "rewrite",
            str(source),
            "--plan",
            str(plan),
            "--out",
            str(rewritten),
            "--apply",
            "--entry",
            "case:main",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert plan_result.returncode == 0, plan_result.stderr
    assert plan.exists()
    assert rewrite_result.returncode == 0, rewrite_result.stderr
    assert "Worker.run(worker, 2)" in rewritten.read_text(encoding="utf-8")


def test_guarded_dispatch_uses_temp_for_receiver_expression_with_side_effects():
    source = (
        "class A:\n"
        "    def run(self): return 'a'\n"
        "class B:\n"
        "    def run(self): return 'b'\n"
        "def make(): return A()\n"
        "def main():\n"
        "    return make().run()\n"
    )
    sites = discover_call_sites(source, filename="case.py")
    target = [site for site in sites if site.method_name == "run"][0]
    observations = [
        ObservationRecord(
            target.call_site_id,
            TypeRef("case", "A", "case.py", False),
            FunctionRef("case", "A.run", "case.py", 2),
            method_name="run",
        ),
        ObservationRecord(
            target.call_site_id,
            TypeRef("case", "B", "case.py", False),
            FunctionRef("case", "B.run", "case.py", 4),
            method_name="run",
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
        source, sites, observations, [verdict]
    )
    rewritten = RewritePlanner(opt_in=True).rewrite_source(source, plans)

    assert len(plans) == 1
    assert plans[0].strategy == "guarded_temp"
    assert "_flatten_receiver_1 = make()" in rewritten
    assert "isinstance(_flatten_receiver_1, B)" in rewritten
    assert "A.run(_flatten_receiver_1)" in rewritten
    assert "make().run()" not in rewritten


def test_rewrite_decision_records_closed_allow_and_open_refusal():
    closed = ClosureVerdict(
        "Worker.run",
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        confidence=0.95,
        evidence=("typing.final",),
    )
    allowed = RewriteDecision.from_verdict(closed)

    assert allowed.allowed is True
    assert allowed.status is ClosureStatus.CLOSED
    assert allowed.confidence == 0.95
    assert allowed.reasons == ("typing.final",)
    assert allowed.blockers == ()

    open_verdict = ClosureVerdict(
        "Worker.run",
        signal="OPEN",
        status=ClosureStatus.OPEN,
        confidence=0.2,
        blockers=("unobserved subclasses",),
    )
    refused = RewriteDecision.from_verdict(open_verdict)

    assert refused.allowed is False
    assert refused.status is ClosureStatus.OPEN
    assert refused.blockers == ("unobserved subclasses",)


def test_planner_exposes_rewrite_decisions_for_closed_and_refused_verdicts():
    closed = ClosureVerdict(
        "Worker.run",
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        evidence=("typing.final",),
    )
    open_verdict = ClosureVerdict(
        "Plugin.run",
        signal="OPEN",
        status=ClosureStatus.OPEN,
        blockers=("external module boundary",),
    )

    decisions = RewritePlanner(opt_in=True).decide([closed, open_verdict])

    assert [decision.method_qualname for decision in decisions] == [
        "Worker.run",
        "Plugin.run",
    ]
    assert [decision.allowed for decision in decisions] == [True, False]
    assert decisions[1].blockers == ("external module boundary",)


def test_cli_plan_emits_rewrite_decisions_for_refused_observations(tmp_path, capsys):
    source = tmp_path / "case.py"
    obs = tmp_path / "obs.json"
    source.write_text(
        "class Worker:\n"
        "    @property\n"
        "    def run(self):\n"
        "        return lambda: 1\n\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run()\n",
        encoding="utf-8",
    )
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source.as_posix()}:7:11-7:23",
                    "receiver_type": {
                        "module": "case",
                        "qualname": "Worker",
                        "file": str(source),
                        "is_builtin": False,
                    },
                    "resolved_function": {
                        "module": "case",
                        "qualname": "Worker.run",
                        "file": str(source),
                        "firstlineno": 3,
                    },
                    "method_name": "run",
                    "frame_module": "case",
                    "order": 1,
                    "input_hash": "case-1",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["rewrite_plans"] == []
    assert payload["rewrite_decisions"][0]["allowed"] is False
    assert payload["rewrite_decisions"][0]["status"] == "unsafe"
    assert payload["rewrite_decisions"][0]["blockers"]


def test_cli_plan_uses_static_subclass_graph_for_local_hierarchy_evidence(tmp_path, capsys):
    source = tmp_path / "case.py"
    obs = tmp_path / "obs.json"
    source.write_text(
        "class Worker:\n"
        "    def run(self):\n"
        "        return 1\n\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run()\n",
        encoding="utf-8",
    )
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source.as_posix()}:7:11-7:23",
                    "receiver_type": {
                        "module": "case",
                        "qualname": "Worker",
                        "file": str(source),
                        "is_builtin": False,
                    },
                    "resolved_function": {
                        "module": "case",
                        "qualname": "Worker.run",
                        "file": str(source),
                        "firstlineno": 2,
                    },
                    "method_name": "run",
                    "frame_module": "case",
                    "order": 1,
                    "input_hash": "case-1",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix()]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["verdicts"][0]["status"] == "open"
    assert payload["rewrite_plans"] == []
    assert "checked static package subclasses" in payload["verdicts"][0]["evidence"]
    assert "checked runtime subclasses" not in payload["verdicts"][0]["evidence"]
