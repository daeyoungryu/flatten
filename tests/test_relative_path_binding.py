import json
import subprocess
import sys


def test_relative_path_trace_plan_rewrite_binds_observations(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        """
from flatten.finals import final

@final
class Shape:
    def area(self):
        return 2

def main():
    s = Shape()
    return s.area()
""".lstrip(),
        encoding="utf-8",
    )
    out = tmp_path / "out.py"

    trace = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "trace",
            "sample.py",
            "--entry",
            "sample:main",
            "--out",
            "obs.json",
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
            "sample.py",
            "--observations",
            "obs.json",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    assert payload["unbound_observations"] == 0
    assert len(payload["rewrite_plans"]) == 1

    rewrite = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "rewrite",
            "sample.py",
            "--observations",
            "obs.json",
            "--out",
            str(out),
            "--apply",
            "--skip-verify",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rewrite.returncode == 0, rewrite.stderr
    assert out.exists()


def test_plan_warns_on_zero_plans_with_unbound_observations_and_strict_fails(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        """
class Shape:
    def area(self):
        return 2
""".lstrip(),
        encoding="utf-8",
    )
    obs = tmp_path / "obs.json"
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": "",
                    "receiver_type": "sample.Shape",
                    "resolved_function": "sample.Shape.area",
                    "method_name": "area",
                    "module": "sample",
                    "qualname": "Shape.area",
                }
            ]
        ),
        encoding="utf-8",
    )

    plan = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "plan",
            str(sample),
            "--observations",
            str(obs),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert plan.returncode == 0
    assert "unbound" in plan.stderr.lower()

    strict = subprocess.run(
        [
            sys.executable,
            "-m",
            "flatten",
            "plan",
            str(sample),
            "--observations",
            str(obs),
            "--strict",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert strict.returncode != 0
    assert "unbound" in strict.stderr.lower()
