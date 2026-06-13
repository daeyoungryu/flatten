from __future__ import annotations

import json
from pathlib import Path

from flatten.cli import main
from flatten.mutations import generate_mutations

BASE_SOURCE = """\
from flatten.finals import final

@final
class Worker:
    def run(self, value):
        return value + 1

def main():
    worker = Worker()
    return worker.run(2)
"""


def test_mutation_harness_generates_required_mutation_kinds() -> None:
    kinds = {mutation.kind for mutation in generate_mutations(BASE_SOURCE)}
    assert {
        "new-subclass",
        "dispatch-target",
        "monkey-patch",
        "runtime-registration",
        "setattr-change",
    } <= kinds


def test_setattr_mutation_blocks_rewrite_false_positive(tmp_path: Path, capsys) -> None:
    mutation = next(
        item for item in generate_mutations(BASE_SOURCE) if item.kind == "setattr-change"
    )
    source = tmp_path / "case.py"
    obs = tmp_path / "obs.json"
    source.write_text(mutation.source, encoding="utf-8")
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

    assert main(["plan", source.as_posix(), "--observations", obs.as_posix()]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rewrite_plans"] == []
    assert payload["verdicts"][0]["status"] == "unsafe"
    assert "setattr" in json.dumps(payload["verdicts"]).lower()
