from __future__ import annotations

import csv
import json
from pathlib import Path

from flatten.benchmarks import load_benchmark_catalog, summarize_benchmark_catalog
from flatten.cli import main


def test_benchmark_catalog_contains_at_least_30_projects() -> None:
    projects = load_benchmark_catalog(Path("benchmarks/projects.csv"))

    assert len(projects) >= 30
    assert {"FastAPI", "Pydantic", "SQLAlchemy", "pytest"} <= {
        project.name for project in projects
    }
    assert all(project.repo_url.startswith("https://") for project in projects)


def test_benchmark_summary_reports_required_kpis() -> None:
    projects = load_benchmark_catalog(Path("benchmarks/projects.csv"))
    summary = summarize_benchmark_catalog(projects)

    assert summary["project_catalog_size"] >= 30
    assert summary["projects_evaluated"] == 0
    for key in [
        "total_call_sites",
        "candidates",
        "rewritten",
        "rejected",
        "unsafe",
        "unknown",
        "false_positives",
        "behavior_mismatches",
        "rewrite_success_rate",
        "proof_coverage",
        "closure_coverage",
    ]:
        assert key in summary


def test_benchmark_cli_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"

    assert (
        main(
            [
                "benchmark",
                "--catalog",
                "benchmarks/projects.csv",
                "--out-json",
                out_json.as_posix(),
                "--out-md",
                out_md.as_posix(),
            ]
        )
        == 0
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["project_catalog_size"] >= 30
    assert "Projects Evaluated" in out_md.read_text(encoding="utf-8")


def test_benchmark_catalog_has_required_csv_columns() -> None:
    with Path("benchmarks/projects.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["name", "package", "repo_url", "category"]


def test_research_evaluation_and_release_gate_docs_exist() -> None:
    text = Path("docs/research_evaluation.md").read_text(encoding="utf-8")
    for heading in [
        "Threats to Validity",
        "Known Unsound Cases",
        "False Positive Analysis",
        "False Negative Analysis",
        "Benchmark Methodology",
        "Reproducibility Guide",
        "Artifact Evaluation Guide",
        "Release Gate",
    ]:
        assert heading in text

    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Project Catalog Size" in readme
    assert "False Positives" in readme
