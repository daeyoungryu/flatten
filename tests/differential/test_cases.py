import importlib.util
import json
from pathlib import Path
from typing import Any

import libcst as cst

from flatten.closure import ClosureChecker
from flatten.contracts import ClosureStatus
from flatten.planner import RewritePlanner

CASE_DIR = Path(__file__).parent


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"_diff_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_differential_policy_cases_match_expected_reason_codes():
    cases = sorted(
        path for path in CASE_DIR.iterdir() if path.is_dir() and (path / "input.py").exists()
    )
    assert len(cases) >= 20
    documented_codes = Path("docs/REWRITE_POLICY.md").read_text(encoding="utf-8")
    for case_dir in cases:
        source = (case_dir / "input.py").read_text(encoding="utf-8")
        expected = json.loads((case_dir / "expected_policy.json").read_text(encoding="utf-8"))
        cst.parse_module(source)
        module = _load_module(case_dir / "input.py")
        verdict = ClosureChecker().check(module.METHOD, module.observed_types())
        decision = RewritePlanner(opt_in=True).decide([verdict])[0]
        assert decision.allowed is expected["allowed"], case_dir.name
        assert decision.reason_code == expected["reason_code"], case_dir.name
        assert expected["reason_code"] in documented_codes
        if not expected["allowed"]:
            assert verdict.status in {
                ClosureStatus.OPEN,
                ClosureStatus.UNSAFE,
                ClosureStatus.UNKNOWN,
            }
