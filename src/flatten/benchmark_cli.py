"""Benchmark-related CLI command implementations."""

from __future__ import annotations

import argparse

from flatten._cli_io import _json_print
from flatten.benchmarks import (
    load_benchmark_catalog,
    summarize_benchmark_catalog,
    write_benchmark_reports,
)


def cmd_benchmark_catalog(args: argparse.Namespace) -> int:
    """Run benchmark catalog checks and write catalog-only summary reports."""
    projects = load_benchmark_catalog(args.catalog.resolve())
    summary = summarize_benchmark_catalog(projects)
    write_benchmark_reports(
        summary,
        out_json=args.out_json.resolve() if args.out_json else None,
        out_md=args.out_md.resolve() if args.out_md else None,
    )
    _json_print(summary)
    return 0
