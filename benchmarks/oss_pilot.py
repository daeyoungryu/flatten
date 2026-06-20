"""Static OSS pilot evaluator for pinned source checkouts."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from libcst import ParserSyntaxError

from flatten.discovery import discover_call_sites

DEFAULT_PROJECTS = ("Click", "attrs", "Requests")
EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def evaluate_python_tree(root: Path) -> dict[str, Any]:
    python_files = _python_files(root)
    parsed_files = 0
    parse_failures = 0
    total_call_sites = 0

    for path in python_files:
        try:
            call_sites = discover_call_sites(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
        except (OSError, ParserSyntaxError, UnicodeDecodeError):
            parse_failures += 1
            continue
        parsed_files += 1
        total_call_sites += len(call_sites)

    return {
        "python_files": len(python_files),
        "parsed_files": parsed_files,
        "parse_failures": parse_failures,
        "total_call_sites": total_call_sites,
        "candidates": total_call_sites,
        "rewritten": 0,
        "rejected": 0,
        "unsafe": 0,
        "unknown": total_call_sites,
        "false_positives": 0,
        "behavior_mismatches": 0,
        "status": "pilot-static-only; no tracing or rewrites attempted",
    }


def run_pilot(
    catalog: Path,
    *,
    project_names: tuple[str, ...] = DEFAULT_PROJECTS,
) -> dict[str, Any]:
    projects = _catalog_subset(catalog, project_names)
    with tempfile.TemporaryDirectory(prefix="flatten-oss-pilot-") as directory:
        root = Path(directory)
        evaluated = []
        for project in projects:
            checkout = root / project["package"]
            commit = _clone_default_head(project["repo_url"], checkout)
            metrics = evaluate_python_tree(checkout)
            evaluated.append({**project, "commit": commit, **metrics})

    totals = {
        "projects_evaluated": len(evaluated),
        "total_call_sites": sum(int(project["total_call_sites"]) for project in evaluated),
        "candidates": sum(int(project["candidates"]) for project in evaluated),
        "rewritten": 0,
        "rejected": 0,
        "unsafe": 0,
        "unknown": sum(int(project["unknown"]) for project in evaluated),
        "false_positives": 0,
        "behavior_mismatches": 0,
    }
    return {
        "schema_version": 1,
        "status": "pilot-static-only; no tracing or rewrites attempted",
        "projects": evaluated,
        **totals,
    }


def write_reports(result: dict[str, Any], *, out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_to_markdown(result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=Path("benchmarks/projects.csv"))
    parser.add_argument("--projects", nargs="+", default=list(DEFAULT_PROJECTS))
    parser.add_argument("--out-json", type=Path, default=Path("benchmarks/oss_pilot.json"))
    parser.add_argument("--out-md", type=Path, default=Path("benchmarks/oss_pilot.md"))
    args = parser.parse_args(argv)

    result = run_pilot(args.catalog, project_names=tuple(args.projects))
    write_reports(result, out_json=args.out_json, out_md=args.out_md)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def _catalog_subset(catalog: Path, names: tuple[str, ...]) -> list[dict[str, str]]:
    wanted = set(names)
    with catalog.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = [row for row in rows if row.get("name") in wanted]
    missing = wanted - {row["name"] for row in selected}
    if missing:
        raise ValueError(f"missing benchmark catalog projects: {sorted(missing)}")
    return selected


def _clone_default_head(repo_url: str, checkout: Path) -> str:
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(checkout)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        text=True,
    ).strip()


def _to_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# OSS Pilot Static Evaluation",
        "",
        "Status: pilot-static-only; no tracing or rewrites attempted.",
        "",
        "| KPI | Value |",
        "| --- | --- |",
        f"| Projects Evaluated | {result['projects_evaluated']} |",
        f"| Total Call Sites | {result['total_call_sites']} |",
        f"| Candidates | {result['candidates']} |",
        f"| Rewritten | {result['rewritten']} |",
        f"| Unknown | {result['unknown']} |",
        f"| False Positives | {result['false_positives']} |",
        f"| Behavior Mismatches | {result['behavior_mismatches']} |",
        "",
        "## Projects",
        "",
        "| Project | Commit | Python Files | Parsed Files | Parse Failures | Call Sites |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for project in result["projects"]:
        lines.append(
            "| {name} | {commit} | {python_files} | {parsed_files} | "
            "{parse_failures} | {total_call_sites} |".format(**project)
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
