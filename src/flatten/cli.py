"""Command line interface for flatten."""

from __future__ import annotations

import argparse

from flatten.report import AnalysisReport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flatten")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--format", choices=["json", "html"], default="json")
    args = parser.parse_args(argv)

    if args.command == "analyze":
        report = AnalysisReport([], confidence=0.0)
        if args.format == "html":
            print(report.to_html())
        else:
            print(report.to_json())
        return 0
    return 2
