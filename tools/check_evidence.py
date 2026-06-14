"""CI evidence gate for benchmark outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from benchmarks.metrics import compare_to_baseline

    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--baseline", type=Path, default=Path("benchmarks/baseline.json"))
    args = parser.parse_args(argv)
    payload = json.loads(args.results.read_text(encoding="utf-8"))
    metrics: dict[str, Any] = payload["metrics"]
    failures: list[str] = []
    if payload.get("schema_invalid_count") != 0:
        failures.append(f"schema_invalid_count={payload.get('schema_invalid_count')}")
    for key in ("false_positive", "unsafe_rewrite_count"):
        if metrics.get(key) != 0:
            failures.append(f"{key}={metrics.get(key)}")
    if not args.results.exists():
        failures.append(f"missing results file: {args.results}")
    if args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        regression = compare_to_baseline(metrics, baseline)
        failures.extend(regression["failures"])
    if failures:
        for failure in failures:
            print(f"evidence gate failed: {failure}", file=sys.stderr)
        return 1
    print(
        "evidence gate passed: "
        f"total_cases={metrics['total_cases']} "
        f"false_positive={metrics['false_positive']} "
        f"unsafe_rewrite_count={metrics['unsafe_rewrite_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
