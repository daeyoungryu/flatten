from __future__ import annotations

import json
from pathlib import Path

from benchmarks.metrics import calculate_metrics
from benchmarks.runner import main, run_benchmarks


def test_benchmark_case_schema_validation() -> None:
    result = run_benchmarks()

    assert result["schema_invalid_count"] == 0
    assert result["metrics"]["total_cases"] >= 50
    assert result["metrics"]["unsafe_case_count"] >= 15
    assert result["metrics"]["dynamic_risk_case_count"] >= 10
    assert result["metrics"]["equivalence_case_count"] >= 10
    assert result["metrics"]["unsupported_cases"] >= 5


def test_metrics_calculation_correctness() -> None:
    cases = [
        {
            "id": "tp",
            "category": "safe",
            "features": ["final_class"],
            "expected_decision": "rewrite",
            "expected_safety": "safe",
            "expected_runtime_equivalence": "pass",
            "actual_decision": "rewrite",
            "actual_runtime_equivalence": "pass",
        },
        {
            "id": "tn",
            "category": "unsafe",
            "features": ["monkey_patching"],
            "expected_decision": "reject",
            "expected_safety": "unsafe",
            "expected_runtime_equivalence": "not_applicable",
            "actual_decision": "reject",
            "actual_runtime_equivalence": "not_applicable",
        },
        {
            "id": "fp",
            "category": "unsafe",
            "features": ["dynamic_subclass_creation"],
            "expected_decision": "reject",
            "expected_safety": "unsafe",
            "expected_runtime_equivalence": "not_applicable",
            "actual_decision": "rewrite",
            "actual_runtime_equivalence": "not_applicable",
        },
        {
            "id": "fn",
            "category": "safe",
            "features": ["sealed_hierarchy"],
            "expected_decision": "rewrite",
            "expected_safety": "safe",
            "expected_runtime_equivalence": "pass",
            "actual_decision": "reject",
            "actual_runtime_equivalence": "not_applicable",
        },
    ]

    metrics = calculate_metrics(cases)

    assert metrics["true_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["unsafe_rewrite_count"] == 1


def test_benchmark_runner_produces_json(tmp_path: Path) -> None:
    output = tmp_path / "benchmark-results.json"

    assert main(["--format", "json", "--output", output.as_posix()]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["metrics"]["total_cases"] >= 50
    assert payload["metrics"]["false_positive"] == 0
    assert payload["metrics"]["unsafe_rewrite_count"] == 0


def test_benchmark_runner_produces_markdown(tmp_path: Path) -> None:
    output = tmp_path / "benchmark-report.md"

    assert main(["--format", "markdown", "--output", output.as_posix()]) == 0

    report = output.read_text(encoding="utf-8")
    assert "# Benchmark Report" in report
    assert "## False Positives" in report
    assert "## Reproduction Command" in report


def test_unsafe_cases_are_not_rewritten() -> None:
    result = run_benchmarks()
    unsafe_rewrites = [
        case
        for case in result["cases"]
        if case["expected_safety"] == "unsafe" and case["actual_decision"] == "rewrite"
    ]

    assert unsafe_rewrites == []


def test_known_safe_cases_rewrite_or_explain_rejection() -> None:
    result = run_benchmarks()
    failures = [
        case["id"]
        for case in result["cases"]
        if case["expected_decision"] == "rewrite"
        and case["actual_decision"] != "rewrite"
        and not case["notes"]
    ]

    assert failures == []


def test_false_positive_count_is_zero_for_current_supported_set() -> None:
    result = run_benchmarks()

    assert result["metrics"]["false_positive"] == 0
