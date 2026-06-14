"""Executable safety benchmark runner."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, cast

from benchmarks.metrics import calculate_metrics, compare_to_baseline
from benchmarks.report import render_markdown
from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision
from flatten.harness import assert_modules_equivalent_subprocess

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"
BASELINE = ROOT / "baseline.json"

REQUIRED_FIELDS = {
    "id",
    "category",
    "description",
    "expected_decision",
    "expected_safety",
    "expected_runtime_equivalence",
    "features",
    "closure_status",
}


def run_benchmarks(
    *,
    cases_dir: Path = CASES_DIR,
    baseline_path: Path = BASELINE,
) -> dict[str, Any]:
    raw_cases = load_cases(cases_dir)
    invalid = validate_cases(raw_cases)
    evaluated = [_evaluate_case(case) for case in raw_cases if case.get("id") not in invalid]
    metrics = calculate_metrics(evaluated)
    baseline = _load_baseline(baseline_path)
    regression = compare_to_baseline(metrics, baseline)
    false_positives = [
        case
        for case in evaluated
        if case["expected_decision"] != "rewrite" and case["actual_decision"] == "rewrite"
    ]
    false_negatives = [
        case
        for case in evaluated
        if case["expected_decision"] == "rewrite" and case["actual_decision"] != "rewrite"
    ]
    unsupported = [case for case in evaluated if case["actual_decision"] == "unsupported"]
    safety_notes = [
        f"{case['id']}: unsafe case was rewritten"
        for case in evaluated
        if case["expected_safety"] == "unsafe" and case["actual_decision"] == "rewrite"
    ]
    return {
        "schema_version": 1,
        "schema_invalid_count": len(invalid),
        "schema_invalid_cases": sorted(invalid),
        "metrics": metrics,
        "baseline_regression": regression,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "unsupported_cases": unsupported,
        "safety_notes": safety_notes,
        "cases": evaluated,
    }


def load_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path} must contain a JSON list")
        cases.extend(payload)
    return sorted(cases, key=lambda case: str(case["id"]))


def validate_cases(cases: list[dict[str, Any]]) -> set[str]:
    invalid: set[str] = set()
    seen: set[str] = set()
    for index, case in enumerate(cases):
        case_id = str(case.get("id", f"<case-{index}>"))
        if case_id in seen:
            invalid.add(case_id)
        seen.add(case_id)
        if REQUIRED_FIELDS - set(case):
            invalid.add(case_id)
        if case.get("expected_decision") not in {"rewrite", "reject", "unsupported"}:
            invalid.add(case_id)
        if case.get("expected_safety") not in {"safe", "unsafe", "unknown"}:
            invalid.add(case_id)
        if case.get("expected_runtime_equivalence") not in {"pass", "fail", "not_applicable"}:
            invalid.add(case_id)
        if not isinstance(case.get("features"), list) or not case.get("features"):
            invalid.add(case_id)
        try:
            ClosureStatus(str(case.get("closure_status")))
        except ValueError:
            invalid.add(case_id)
    return invalid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_benchmarks()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    else:
        args.output.write_text(render_markdown(result), encoding="utf-8")
    return 1 if result["schema_invalid_count"] else 0


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    verdict = ClosureVerdict(
        method_qualname=str(case.get("method_qualname", f"{case['id']}.run")),
        status=ClosureStatus(str(case["closure_status"])),
        reasons=tuple(case.get("reasons", ())),
        blockers=tuple(case.get("blockers", ())),
        evidence=tuple(case.get("evidence", ())),
    )
    decision = RewriteDecision.from_verdict(verdict)
    actual_decision = _actual_decision(decision)
    actual_equivalence = _run_equivalence_probe(case.get("equivalence_probe"))
    notes = list(decision.blockers or decision.reasons)
    return {
        **case,
        "actual_decision": actual_decision,
        "actual_runtime_equivalence": actual_equivalence,
        "decision_reason_code": decision.reason_code,
        "decision_message": decision.message,
        "notes": notes,
    }


def _actual_decision(decision: RewriteDecision) -> str:
    if decision.allowed:
        return "rewrite"
    if decision.status in {ClosureStatus.UNKNOWN, ClosureStatus.PROBABLY_CLOSED}:
        return "unsupported"
    return "reject"


def _run_equivalence_probe(probe: object) -> str:
    if probe is None:
        return "not_applicable"
    scenario = str(probe)
    original, rewritten = _equivalence_sources(scenario)
    with tempfile.TemporaryDirectory(prefix="flatten-benchmark-") as directory:
        root = Path(directory)
        original_path = root / "original.py"
        rewritten_path = root / "rewritten.py"
        original_path.write_text(original, encoding="utf-8")
        rewritten_path.write_text(rewritten, encoding="utf-8")
        try:
            assert_modules_equivalent_subprocess(
                original_path,
                rewritten_path,
                "entry",
                cases=[{"args": [2], "kwargs": {}}],
                timeout=5.0,
            )
        except AssertionError:
            return "fail"
    return "pass"


def _equivalence_sources(scenario: str) -> tuple[str, str]:
    sources = {
        "equivalent_direct": (
            """
            class Worker:
                def run(self, value):
                    return value + 1
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def run(self, value):
                    return value + 1
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "side_effect_mismatch": (
            """
            events = []
            class Worker:
                def run(self, value):
                    events.append("run")
                    print("side-effect")
                    return value
            def entry(value):
                return Worker().run(value)
            """,
            """
            events = []
            class Worker:
                def run(self, value):
                    events.append("run")
                    return value
            def entry(value):
                return value
            """,
        ),
        "attribute_lookup_mismatch": (
            """
            class Worker:
                def __getattribute__(self, name):
                    if name == "run":
                        return lambda value: value + 10
                    return object.__getattribute__(self, name)
                def run(self, value):
                    return value + 1
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def __getattribute__(self, name):
                    if name == "run":
                        return lambda value: value + 10
                    return object.__getattribute__(self, name)
                def run(self, value):
                    return value + 1
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "descriptor_mismatch": (
            """
            class Descriptor:
                def __get__(self, obj, owner):
                    return lambda value: value + 5
            class Worker:
                run = Descriptor()
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Descriptor:
                def __get__(self, obj, owner):
                    return lambda value: value + 5
            class Worker:
                run = Descriptor()
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "exception_mismatch": (
            """
            class Worker:
                def run(self, value):
                    raise ValueError("original")
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def run(self, value):
                    raise TypeError("rewritten")
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "return_value_mismatch": (
            """
            class Worker:
                def run(self, value):
                    return value + 1
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def run(self, value):
                    return value + 2
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "equivalent_guarded": (
            """
            class Base:
                def run(self, value):
                    return value
            class Child(Base):
                def run(self, value):
                    return value + 3
            def entry(value):
                worker = Child()
                return worker.run(value)
            """,
            """
            class Base:
                def run(self, value):
                    return value
            class Child(Base):
                def run(self, value):
                    return value + 3
            def entry(value):
                worker = Child()
                if isinstance(worker, Child):
                    return Child.run(worker, value)
                return Base.run(worker, value)
            """,
        ),
        "stdout_mismatch": (
            """
            class Worker:
                def run(self, value):
                    print("original")
                    return value
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def run(self, value):
                    print("rewritten")
                    return value
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "equivalent_exception": (
            """
            class Worker:
                def run(self, value):
                    raise ValueError("same")
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def run(self, value):
                    raise ValueError("same")
            def entry(value):
                worker = Worker()
                return Worker.run(worker, value)
            """,
        ),
        "state_mismatch": (
            """
            class Worker:
                def __init__(self):
                    self.value = 1
                def run(self, value):
                    self.value += value
                    return self.value
            def entry(value):
                return Worker().run(value)
            """,
            """
            class Worker:
                def __init__(self):
                    self.value = 1
                def run(self, value):
                    self.value += value
                    return self.value
            def entry(value):
                worker = Worker()
                return value
            """,
        ),
    }
    if scenario not in sources:
        raise ValueError(f"unknown equivalence probe: {scenario}")
    return tuple(textwrap.dedent(source).lstrip() for source in sources[scenario])  # type: ignore[return-value]


def _load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    sys.exit(main())
