"""Deterministic benchmark metric calculations."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def calculate_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    supported = sum(1 for case in cases if case["actual_decision"] != "unsupported")
    unsupported = total - supported
    accepted = sum(1 for case in cases if case["actual_decision"] == "rewrite")
    rejected = sum(1 for case in cases if case["actual_decision"] in {"reject", "unsupported"})
    true_positive = sum(
        1
        for case in cases
        if case["expected_decision"] == "rewrite" and case["actual_decision"] == "rewrite"
    )
    true_negative = sum(
        1
        for case in cases
        if case["expected_decision"] != "rewrite" and case["actual_decision"] != "rewrite"
    )
    false_positive = sum(
        1
        for case in cases
        if case["expected_decision"] != "rewrite" and case["actual_decision"] == "rewrite"
    )
    false_negative = sum(
        1
        for case in cases
        if case["expected_decision"] == "rewrite" and case["actual_decision"] != "rewrite"
    )
    safety_failure_count = sum(
        1
        for case in cases
        if case["expected_safety"] == "unsafe" and case["actual_decision"] == "rewrite"
    )
    equivalence_failures = sum(
        1
        for case in cases
        if case["expected_runtime_equivalence"] != case["actual_runtime_equivalence"]
    )
    feature_counts: dict[str, int] = defaultdict(int)
    for case in cases:
        for feature in case["features"]:
            feature_counts[str(feature)] += 1
    category_breakdown = dict(
        sorted(Counter(case["category"] for case in cases).items())
    )
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "total_cases": total,
        "supported_cases": supported,
        "unsupported_cases": unsupported,
        "rewrite_accepted": accepted,
        "rewrite_rejected": rejected,
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "fpr": _ratio(false_positive, false_positive + true_negative),
        "fnr": _ratio(false_negative, false_negative + true_positive),
        "coverage_by_feature": dict(sorted(feature_counts.items())),
        "category_breakdown": category_breakdown,
        "safety_failure_count": safety_failure_count,
        "unsafe_rewrite_count": safety_failure_count,
        "behavioral_equivalence_failures": equivalence_failures,
        "unsafe_case_count": sum(1 for case in cases if case["expected_safety"] == "unsafe"),
        "dynamic_risk_case_count": sum(
            1
            for case in cases
            if any(
                feature
                in {
                    "dynamic_subclass_creation",
                    "late_import_subclass",
                    "monkey_patching",
                    "method_reassignment",
                    "__getattr__",
                    "__getattribute__",
                    "descriptor",
                    "property",
                    "metaclass_side_effect",
                    "plugin_registry",
                    "abc_virtual_subclass",
                    "protocol_structural_typing",
                    "side_effectful_lookup",
                    "module_reload",
                    "runtime_code_generation",
                }
                for feature in case["features"]
            )
        ),
        "equivalence_case_count": sum(
            1 for case in cases if case["expected_runtime_equivalence"] != "not_applicable"
        ),
    }


def compare_to_baseline(metrics: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline:
        return {"status": "no_baseline", "failures": [], "warnings": []}
    failures: list[str] = []
    warnings: list[str] = []
    for key in ("false_positive", "unsafe_rewrite_count"):
        if metrics[key] > baseline.get(key, 0):
            failures.append(f"{key} increased from {baseline.get(key)} to {metrics[key]}")
    if metrics["total_cases"] < baseline.get("total_cases", 0):
        failures.append(
            f"total_cases decreased from {baseline.get('total_cases')} to {metrics['total_cases']}"
        )
    for key in ("precision", "recall"):
        old = baseline.get(key)
        new = metrics.get(key)
        if isinstance(old, int | float) and isinstance(new, int | float) and new < old:
            warnings.append(f"{key} decreased from {old} to {new}")
    return {
        "status": "failed" if failures else "passed",
        "failures": failures,
        "warnings": warnings,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)
