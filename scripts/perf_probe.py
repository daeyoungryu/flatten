#!/usr/bin/env python3
"""Tracer memory probe: measures dispatch vs. non-dispatch record accumulation.

Usage:
    python scripts/perf_probe.py

Reports the number of total records stored vs. dispatch-only records.
Exits 0 if the tracer stores only dispatch records (ratio == 1.0).
Exits 1 if non-dispatch records are leaking into storage.

This script directly validates the Phase 3 (P2) fix: _record_return and
_flush_pending_as_exception must skip non-dispatch calls.
"""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))

from flatten.tracer import Tracer  # noqa: E402


def _plain_func_a(x: int) -> int:
    return x + 1


def _plain_func_b(x: int) -> int:
    return x * 3


class _DispatchTarget:
    def process(self, x: int) -> int:
        return x ** 2


def main() -> int:
    n_plain = 500
    n_dispatch = 10

    with Tracer() as tracer:
        for i in range(n_plain):
            _plain_func_a(i)
            _plain_func_b(i)
        for i in range(n_dispatch):
            _DispatchTarget().process(i)

    total = len(tracer.records)
    dispatch = sum(1 for r in tracer.records if r.is_dispatch_target)
    non_dispatch = total - dispatch

    print(f"total_records      : {total}")
    print(f"dispatch_records   : {dispatch}")
    print(f"non_dispatch_records: {non_dispatch}")
    print(f"dispatch_ratio     : {dispatch / total:.3f}" if total else "dispatch_ratio: n/a")

    if non_dispatch > 0:
        print(
            f"\nFAIL: {non_dispatch} non-dispatch record(s) leaked into storage.",
            file=sys.stderr,
        )
        print("Fix: add 'if not pending.is_dispatch_target: return' to", file=sys.stderr)
        print(
            "     _record_return() and _flush_pending_as_exception() in tracer.py",
            file=sys.stderr,
        )
        return 1

    print(f"\nPASS: only dispatch records stored ({dispatch} record(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
