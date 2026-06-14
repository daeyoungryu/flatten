import json
import subprocess
import sys

from flatten.confidence import confidence_score
from flatten.contracts import ClosureStatus, ClosureVerdict


def test_confidence_closed_open_and_no_known_impls_are_numeric():
    closed = ClosureVerdict(
        "pkg.Base.f",
        known_impls=[object],
        status=ClosureStatus.CLOSED,
        evidence=("typing.final method",),
    )
    open_verdict = ClosureVerdict(
        "pkg.Base.f",
        known_impls=[object],
        open_signals=["OPEN: incomplete"],
        status=ClosureStatus.OPEN,
    )
    unknown = ClosureVerdict("pkg.Base.f", known_impls=[], status=ClosureStatus.UNKNOWN)

    scores = [
        confidence_score(closed),
        confidence_score(open_verdict),
        confidence_score(unknown),
    ]

    assert all(isinstance(score, float) for score in scores)
    assert scores[0] == 0.95
    assert scores[1] == 0.0
    assert scores[2] == 0.0
    assert all(0.0 <= score <= 1.0 for score in scores)


def test_plan_json_confidence_is_always_number(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        """
from flatten.finals import final

@final
class Only:
    def area(self):
        return 1

def main():
    return Only().area()
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
            str(sample),
            "--entry",
            "sample:main",
            "--out",
            str(obs),
        ],
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
            str(sample),
            "--observations",
            str(obs),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert plan.returncode == 0, plan.stderr
    payload = json.loads(plan.stdout)
    for item in payload["rewrite_plans"]:
        assert isinstance(item["confidence"], float)
        assert 0.0 <= item["confidence"] <= 1.0
