"""Benchmark catalog and KPI report helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkProject:
    name: str
    package: str
    repo_url: str
    category: str

    def to_json(self) -> dict[str, str]:
        return asdict(self)


def load_benchmark_catalog(path: Path) -> list[BenchmarkProject]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["name", "package", "repo_url", "category"]:
            raise ValueError("benchmark catalog must use name,package,repo_url,category")
        projects: list[BenchmarkProject] = []
        for index, row in enumerate(reader, start=2):
            project = BenchmarkProject(
                name=str(row.get("name", "")).strip(),
                package=str(row.get("package", "")).strip(),
                repo_url=str(row.get("repo_url", "")).strip(),
                category=str(row.get("category", "")).strip(),
            )
            if not all(project.to_json().values()):
                raise ValueError(f"benchmark catalog row {index} has empty fields")
            if not project.repo_url.startswith("https://"):
                raise ValueError(f"benchmark catalog row {index} repo_url must be https")
            projects.append(project)
    return projects


def summarize_benchmark_catalog(projects: list[BenchmarkProject]) -> dict[str, Any]:
    return {
        "project_catalog_size": len(projects),
        "projects_evaluated": 0,
        "total_call_sites": 0,
        "candidates": 0,
        "rewritten": 0,
        "rejected": 0,
        "unsafe": 0,
        "unknown": 0,
        "false_positives": 0,
        "behavior_mismatches": 0,
        "rewrite_success_rate": None,
        "proof_coverage": None,
        "closure_coverage": None,
        "projects": [project.to_json() for project in projects],
        "status": "catalog-only; no OSS source checkout evaluated",
    }


def write_benchmark_reports(
    summary: dict[str, Any],
    *,
    out_json: Path | None = None,
    out_md: Path | None = None,
) -> None:
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(_summary_to_markdown(summary), encoding="utf-8")


def _summary_to_markdown(summary: dict[str, Any]) -> str:
    labels = [
        ("Projects Evaluated", "projects_evaluated"),
        ("Project Catalog Size", "project_catalog_size"),
        ("Total Call Sites", "total_call_sites"),
        ("Candidates", "candidates"),
        ("Rewritten", "rewritten"),
        ("Rejected", "rejected"),
        ("Unsafe", "unsafe"),
        ("Unknown", "unknown"),
        ("False Positives", "false_positives"),
        ("Behavior Mismatches", "behavior_mismatches"),
        ("Rewrite Success Rate", "rewrite_success_rate"),
        ("Proof Coverage", "proof_coverage"),
        ("Closure Coverage", "closure_coverage"),
    ]
    lines = ["# Benchmark Summary", "", "| KPI | Value |", "| --- | --- |"]
    for label, key in labels:
        value = summary.get(key)
        lines.append(f"| {label} | {'n/a' if value is None else value} |")
    lines.extend(
        [
            "",
            f"Status: {summary.get('status', '')}",
            "release-gate: catalog-only benchmark report generated",
            "",
        ]
    )
    return "\n".join(lines)
