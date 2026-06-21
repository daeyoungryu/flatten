"""Command line interface for flatten."""

from __future__ import annotations

import argparse
from pathlib import Path

# Re-export for backwards compatibility and test imports
from flatten._cli_io import _load_cases, _load_module  # noqa: F401
from flatten._cli_orchestration import (
    _make_plans,  # noqa: F401
    _observation_from_trace,  # noqa: F401
    _verdicts_from_observations,  # noqa: F401
    cmd_analyze,
    cmd_benchmark,
    cmd_evaluate,
    cmd_expand,
    cmd_plan,
    cmd_report,
    cmd_rewrite,
    cmd_specialize,
    cmd_trace,
    cmd_verify,
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the flatten CLI argument parser."""
    parser = argparse.ArgumentParser(prog="flatten")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("path", type=Path, nargs="?")
    analyze.add_argument("--format", choices=["json", "html"], default="json")
    analyze.add_argument("--json", action="store_const", dest="format", const="json")
    analyze.add_argument("--strict", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    expand = subparsers.add_parser("expand")
    expand.add_argument("path", type=Path)
    expand.add_argument("--target", required=True)
    expand.set_defaults(func=cmd_expand)

    trace = subparsers.add_parser("trace")
    trace.add_argument("path", type=Path)
    trace.add_argument("--entry", required=True)
    trace.add_argument("--out", type=Path)
    trace.add_argument("--json", action="store_true")
    trace.add_argument("--strict", action="store_true")
    trace.add_argument("--capture-values", action="store_true")
    trace.set_defaults(func=cmd_trace)

    plan = subparsers.add_parser("plan")
    plan.add_argument("path", type=Path)
    plan.add_argument("--observations", type=Path, required=True)
    plan.add_argument("--out", type=Path)
    plan.add_argument("--closed-world", action="store_true")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--strict", action="store_true")
    plan.set_defaults(func=cmd_plan)

    rewrite = subparsers.add_parser("rewrite")
    rewrite.add_argument("path", type=Path)
    rewrite.add_argument("--observations", type=Path)
    rewrite.add_argument("--plan", type=Path)
    rewrite.add_argument("--out", type=Path, required=True)
    rewrite.add_argument("--apply", action="store_true")
    rewrite.add_argument("--dry-run", action="store_true")
    rewrite.add_argument("--closed-world", action="store_true")
    rewrite.add_argument("--entry")
    rewrite.add_argument("--cases", type=Path)
    rewrite.add_argument("--skip-verify", action="store_true")
    rewrite.add_argument("--json", action="store_true")
    rewrite.add_argument(
        "--strict",
        action="store_true",
        help="exit code 2 if rewrites were skipped due to low confidence (only with --strict)",
    )
    rewrite.set_defaults(func=cmd_rewrite)

    verify = subparsers.add_parser("verify")
    verify.add_argument("original", type=Path)
    verify.add_argument("rewritten", type=Path)
    verify.add_argument("--entry", required=True)
    verify.add_argument("--cases", type=Path)
    verify.add_argument("--json", action="store_true")
    verify.add_argument("--strict", action="store_true")
    verify.set_defaults(func=cmd_verify)

    report = subparsers.add_parser("report")
    report.add_argument("plan", type=Path)
    report.add_argument("--json", action="store_true")
    report.add_argument("--strict", action="store_true")
    report.set_defaults(func=cmd_report)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--plan", type=Path)
    evaluate.add_argument("--json", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)

    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--catalog", type=Path, required=True)
    benchmark.add_argument("--out-json", type=Path)
    benchmark.add_argument("--out-md", type=Path)
    benchmark.add_argument("--json", action="store_true")
    benchmark.set_defaults(func=cmd_benchmark)

    specialize = subparsers.add_parser("specialize")
    specialize.add_argument("path", type=Path)
    specialize.add_argument("--entry", required=True)
    specialize.add_argument("--target", required=True)
    specialize.add_argument("--args-json", type=Path, required=True)
    specialize.add_argument("--out", type=Path, required=True)
    specialize.set_defaults(func=cmd_specialize)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the flatten CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        import sys

        print(f"flatten: error: {exc}", file=sys.stderr)
        return 1
