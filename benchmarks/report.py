"""Markdown report rendering for benchmark results."""

from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Benchmark Report",
        "",
        "## Summary",
        "",
        f"- Total cases: {metrics['total_cases']}",
        f"- Supported cases: {metrics['supported_cases']}",
        f"- Unsupported cases: {metrics['unsupported_cases']}",
        f"- False positives: {metrics['false_positive']}",
        f"- Unsafe rewrites: {metrics['unsafe_rewrite_count']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key in (
        "rewrite_accepted",
        "rewrite_rejected",
        "true_positive",
        "true_negative",
        "false_positive",
        "false_negative",
        "precision",
        "recall",
        "fpr",
        "fnr",
        "safety_failure_count",
        "behavioral_equivalence_failures",
    ):
        lines.append(f"| {key} | {_display(metrics[key])} |")
    lines.extend(["", "## Category Breakdown", "", "| Category | Cases |", "| --- | ---: |"])
    for category, count in metrics["category_breakdown"].items():
        lines.append(f"| {category} | {count} |")
    lines.extend(["", "## Coverage By Feature", "", "| Feature | Cases |", "| --- | ---: |"])
    for feature, count in metrics["coverage_by_feature"].items():
        lines.append(f"| `{feature}` | {count} |")
    lines.extend(_case_section("False Positives", result["false_positives"]))
    lines.extend(_case_section("False Negatives", result["false_negatives"]))
    lines.extend(_case_section("Unsupported Cases", result["unsupported_cases"]))
    lines.extend(["", "## Safety Notes", ""])
    if result["safety_notes"]:
        lines.extend(f"- {note}" for note in result["safety_notes"])
    else:
        lines.append("- No safety failures detected by this benchmark run.")
    regression = result["baseline_regression"]
    lines.extend(
        [
            "",
            "## Regression Compared To Baseline",
            "",
            f"- Status: {regression['status']}",
        ]
    )
    for failure in regression["failures"]:
        lines.append(f"- Failure: {failure}")
    for warning in regression["warnings"]:
        lines.append(f"- Warning: {warning}")
    lines.extend(
        [
            "",
            "## Reproduction Command",
            "",
            "```powershell",
            "python -m benchmarks.runner --format json --output benchmark-results.json",
            "python -m benchmarks.runner --format markdown --output benchmark-report.md",
            "python tools/check_evidence.py benchmark-results.json",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _case_section(title: str, cases: list[dict[str, Any]]) -> list[str]:
    lines = ["", f"## {title}", ""]
    if not cases:
        lines.append("- None")
        return lines
    for case in cases:
        lines.append(
            f"- `{case['id']}`: expected `{case['expected_decision']}`, "
            f"actual `{case['actual_decision']}`; {case['description']}"
        )
    return lines


def _display(value: Any) -> str:
    return "n/a" if value is None else str(value)

