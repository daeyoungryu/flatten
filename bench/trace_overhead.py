"""Tracer overhead benchmark — compares global vs. local-events tracing.

Measures:
  - baseline: untraced Python method calls
  - global_trace: Tracer(target=None) using sys.monitoring.set_events (all calls)
  - local_trace:  Tracer(target=fn)  using sys.monitoring.set_local_events

Target: local_trace overhead ratio <= 40x vs baseline.

Usage:
    python bench/trace_overhead.py
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flatten.tracer import Tracer  # noqa: E402


class _Target:
    """Subject class whose method we trace."""

    def work(self, x: int) -> int:
        return x + 1


def _measure(fn: Callable[[], object], n: int) -> float:
    """Return microseconds per call for n calls of fn()."""
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1e6


def main() -> int:
    N = 20_000
    obj = _Target()

    # --- baseline (no tracing) ---
    baseline_us = _measure(lambda: obj.work(1), N)

    # --- global events (no target → set_events on all code objects) ---
    tr_global = Tracer(capture_values=False)
    tr_global.start()
    global_us = _measure(lambda: obj.work(1), N)
    tr_global.stop()

    # --- local events (target set → set_local_events for _Target.work only) ---
    tr_local = Tracer(_Target.work, capture_values=False)
    tr_local.start()
    local_us = _measure(lambda: obj.work(1), N)
    tr_local.stop()

    ratio_global = global_us / baseline_us if baseline_us > 0 else float("inf")
    ratio_local = local_us / baseline_us if baseline_us > 0 else float("inf")

    print(f"baseline (no trace): {baseline_us:.2f} us/call")
    print(f"global events:       {global_us:.2f} us/call  ({ratio_global:.1f}x)")
    print(f"local  events:       {local_us:.2f} us/call  ({ratio_local:.1f}x)")

    TARGET = 40.0
    ok = ratio_local <= TARGET
    status = "PASS" if ok else "FAIL"
    print(f"{status}  local-events ratio {ratio_local:.1f}x (target <= {TARGET}x)")

    result = {
        "baseline_us": round(baseline_us, 3),
        "global_trace_us": round(global_us, 3),
        "local_trace_us": round(local_us, 3),
        "ratio_global": round(ratio_global, 1),
        "ratio_local": round(ratio_local, 1),
        "target_ratio": TARGET,
        "passed": ok,
    }
    import json
    out = Path(__file__).parent.parent / "AI" / "reviews" / "0.2.0" / "trace_overhead.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
