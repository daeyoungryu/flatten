from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from flatten.benchmarks import load_benchmark_catalog, summarize_benchmark_catalog
from flatten.cli import build_parser, main


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


def test_benchmark_catalog_cli_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"

    assert (
        main(
            [
                "benchmark-catalog",
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
    assert payload["status"] == "catalog-only; no OSS source checkout evaluated"
    assert "Catalog-only" in out_md.read_text(encoding="utf-8")


def test_benchmark_help_labels_legacy_command_as_catalog_alias(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["benchmark", "--help"])

    assert exc.value.code == 0
    assert "alias for benchmark-catalog" in capsys.readouterr().out


def test_benchmark_catalog_handler_lives_outside_general_cli_orchestration() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["benchmark-catalog", "--catalog", "benchmarks/projects.csv"]
    )

    assert args.func.__module__ == "flatten.benchmark_cli"


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


def test_readme_distinguishes_catalog_from_oss_pilot() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    pilot = json.loads(Path("benchmarks/oss_pilot.json").read_text(encoding="utf-8"))

    assert "Catalog-only status" in readme
    assert "OSS Pilot Static Evaluation" in readme
    assert str(pilot["projects_evaluated"]) in readme
    assert str(pilot["total_call_sites"]) in readme
