"""Orchestrate the read-only Capafy audit pipeline."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

try:
    from scripts.capafy_audit_report import render_summary
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root.
    from capafy_audit_report import render_summary


class AuditCommandError(RuntimeError):
    """A whitelisted audit subprocess failed."""

    def __init__(self, stage: str, returncode: int) -> None:
        super().__init__(f"{stage} failed with exit code {returncode}")
        self.returncode = returncode


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _artifact(output_dir: Path, name: str) -> Path:
    path = output_dir / name
    if not _inside(path, output_dir):
        raise ValueError(f"audit artifact escapes output directory: {name}")
    return path


def filtered_status(snapshot: str) -> tuple[str, ...]:
    """Remove the audit's own untracked output from a porcelain snapshot."""
    return tuple(
        line
        for line in snapshot.splitlines()
        if ".capafy-audit/" not in line.replace("\\", "/")
    )


def status_diff(before: str, after: str) -> str:
    """Return a unified diff of filtered Git status snapshots."""
    return "\n".join(
        difflib.unified_diff(
            filtered_status(before),
            filtered_status(after),
            fromfile="pre-audit",
            tofile="post-audit",
            lineterm="",
        )
    )


def _run(command: Sequence[str], *, cwd: Path, stage: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command), cwd=cwd, text=True, capture_output=True, check=False
    )
    if result.returncode:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise AuditCommandError(stage, result.returncode)
    return result


def _git_snapshot(repo: Path) -> str:
    return _run(
        ["git", "status", "--porcelain"], cwd=repo, stage="git status"
    ).stdout


def _is_git_repo(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def run_audit(
    scope: Path,
    *,
    repo: Path | None = None,
    entry: str | None = None,
    yes_execute_trace: bool = False,
) -> dict[str, object]:
    """Run static-only audit by default, or the full gated pipeline."""
    repo = (repo or Path.cwd()).resolve()
    scope = scope.resolve()
    if not _inside(scope, repo):
        raise ValueError("scope must be inside the target repository")
    git_available = _is_git_repo(repo)
    if not git_available:
        print(
            "WARNING: target is not a Git repository; mutation safety net unavailable",
            file=sys.stderr,
        )
    pre_status = _git_snapshot(repo) if git_available else ""

    output_root = repo / ".capafy-audit"
    output_dir = output_root / _timestamp()
    if not _inside(output_dir, output_root):
        raise ValueError("generated output directory escaped audit root")
    output_dir.mkdir(parents=True, exist_ok=False)

    _run([sys.executable, "-c", "import flatten"], cwd=repo, stage="preflight import")
    analyze_path = _artifact(output_dir, "analyze.json")
    analyze = _run(
        [sys.executable, "-m", "flatten", "analyze", str(scope), "--json"],
        cwd=repo,
        stage="analyze",
    )
    json.loads(analyze.stdout)
    analyze_path.write_text(analyze.stdout, encoding="utf-8")

    result: dict[str, object] = {
        "output_dir": str(output_dir),
        "trace_executed": False,
        "git_warning": False,
    }
    if yes_execute_trace:
        if not entry:
            raise ValueError("--entry is required when trace execution is enabled")
        observations = _artifact(output_dir, "observations.json")
        plan = _artifact(output_dir, "plan.json")
        report = _artifact(output_dir, "report.json")
        summary = _artifact(output_dir, "summary.md")
        _run(
            [
                sys.executable,
                "-m",
                "flatten",
                "trace",
                str(scope),
                "--entry",
                entry,
                "--out",
                str(observations),
            ],
            cwd=repo,
            stage="trace",
        )
        _run(
            [
                sys.executable,
                "-m",
                "flatten",
                "plan",
                str(scope),
                "--observations",
                str(observations),
                "--out",
                str(plan),
            ],
            cwd=repo,
            stage="plan",
        )
        report_result = _run(
            [sys.executable, "-m", "flatten", "report", str(plan), "--json"],
            cwd=repo,
            stage="report",
        )
        json.loads(report_result.stdout)
        report.write_text(report_result.stdout, encoding="utf-8")
        render_summary(report, summary)
        result["trace_executed"] = True
        result["report"] = str(report)
        result["summary"] = str(summary)

    post_status = _git_snapshot(repo) if git_available else ""
    mutation_diff = status_diff(pre_status, post_status) if git_available else ""
    if mutation_diff:
        warning = "WARNING: REPOSITORY CHANGED DURING AUDIT\n" + mutation_diff
        print(warning)
        result["git_warning"] = True
        result["git_status_diff"] = mutation_diff
        if yes_execute_trace:
            render_summary(
                _artifact(output_dir, "report.json"),
                _artifact(output_dir, "summary.md"),
                git_warning=mutation_diff,
            )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", type=Path)
    parser.add_argument("--entry")
    parser.add_argument("--yes-execute-trace", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_audit(
            args.scope,
            entry=args.entry,
            yes_execute_trace=args.yes_execute_trace,
        )
    except AuditCommandError as exc:
        return exc.returncode or 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"capafy audit: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
