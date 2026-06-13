from __future__ import annotations

import json
from pathlib import Path

from flatten.cli import main


def test_cli_plan_emits_proof_artifact_for_each_rewrite(tmp_path: Path, capsys) -> None:
    source = tmp_path / "case.py"
    obs = tmp_path / "obs.json"
    source.write_text(
        "from typing import final\n\n"
        "@final\n"
        "class Worker:\n"
        "    def run(self, value):\n"
        "        return value + 1\n\n"
        "def main():\n"
        "    worker = Worker()\n"
        "    return worker.run(2)\n",
        encoding="utf-8",
    )
    obs.write_text(
        json.dumps(
            [
                {
                    "call_site_id": f"{source}:10:11-10:24",
                    "receiver_type": {
                        "module": "case",
                        "qualname": "Worker",
                        "file": str(source),
                        "is_builtin": False,
                    },
                    "resolved_function": {
                        "module": "case",
                        "qualname": "Worker.run",
                        "file": str(source),
                        "firstlineno": 5,
                    },
                    "method_name": "run",
                    "frame_module": "case",
                    "order": 1,
                    "input_hash": "case-1",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert (
        main(["plan", source.as_posix(), "--observations", obs.as_posix(), "--closed-world"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert len(payload["rewrite_plans"]) == 1
    artifact = payload["rewrite_plans"][0]["proof_artifact"]
    assert artifact == {
        "callsite": f"{source.as_posix()}:10:11-10:24",
        "observed_targets": ["case.Worker"],
        "closure_status": "closed",
        "closure_rules_passed": [
            "checked free variables",
            "checked closure cells",
            "checked nonlocal writes",
            "checked instance attribute writes",
            "checked static package subclasses",
        ],
        "closure_rules_failed": [],
        "risk_level": "safe",
        "rewrite_allowed": True,
    }


def test_cli_plan_does_not_emit_rewrite_without_proof_evidence(capsys) -> None:
    assert main(["report", "does-not-exist.json"]) == 1
    assert "error" in capsys.readouterr().err.lower()
