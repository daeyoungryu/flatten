#!/usr/bin/env python3
"""SI gate: run test_si_regressions.py and report pass/fail.

Usage:
    python scripts/si_gate.py [--full]

    --full   also run the complete test suite (python -m pytest tests/ -q)

Exits 0 when all required tests pass.
Exits 1 on any failure.

Definition of Done (v0.2.1):
  - 8 tests in test_si_regressions.py all GREEN (7 SI fixes + 1 META)
  - All pre-existing tests still GREEN (no regressions)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_REGRESSION_FILE = _ROOT / "tests" / "test_si_regressions.py"


def run(cmd: list[str], *, label: str) -> int:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=_ROOT)
    return result.returncode


def main() -> int:
    full = "--full" in sys.argv

    if not _REGRESSION_FILE.exists():
        print(f"ERROR: gate file not found: {_REGRESSION_FILE}", file=sys.stderr)
        return 1

    rc_reg = run(
        [sys.executable, "-m", "pytest", str(_REGRESSION_FILE), "-v"],
        label="SI Regression Tests (test_si_regressions.py)",
    )

    if full:
        rc_full = run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
            label="Full Test Suite",
        )
    else:
        rc_full = 0
        print("\n(skipping full suite - pass --full to enable)")

    rc_ruff = run(
        [sys.executable, "-m", "ruff", "check", "src/flatten/"],
        label="Ruff lint (src/flatten/)",
    )

    rc_mypy = run(
        [sys.executable, "-m", "mypy", "--strict", "src/flatten/"],
        label="Mypy strict (src/flatten/)",
    )

    print(f"\n{'=' * 60}")
    print("  SI Gate Summary")
    print(f"{'=' * 60}")
    _status("SI regression tests", rc_reg)
    if full:
        _status("Full test suite", rc_full)
    _status("Ruff lint", rc_ruff)
    _status("Mypy strict", rc_mypy)

    overall = rc_reg | rc_full | rc_ruff | rc_mypy
    print()
    if overall == 0:
        print("GATE PASSED - all checks green.")
    else:
        print("GATE FAILED - see errors above.", file=sys.stderr)
    return min(overall, 1)


def _status(label: str, rc: int) -> None:
    mark = "PASS" if rc == 0 else "FAIL"
    print(f"  [{mark}]  {label}")


if __name__ == "__main__":
    sys.exit(main())
