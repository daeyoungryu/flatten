"""P0 repro tests.

On flatten-polymorph 0.1.1, T1-T3 are RED and T4 is GREEN.
After T1-T3 fixes, all tests in this file must be GREEN.

Run:
    python -m pytest tests/regression/test_p0_repro.py -v
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "flatten", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=60,
    )


UNSOUND_SRC = textwrap.dedent(
    """
    import random
    from flatten.finals import final

    @final
    class Worker:
        def run(self, v):
            return v + 1

    class Animal:
        def speak(self):
            return "..."

    class Dog(Animal):
        def speak(self):
            return "woof"

    class Cat(Animal):
        def speak(self):
            return "meow"

    def make():
        return Dog() if random.random() < 2 else Cat()  # trace observes Dog only

    def main():
        a = Worker().run(2)
        pet = make()
        b = pet.speak()
        return (a, b)
    """
)


@pytest.fixture()
def unsound_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    src = tmp_path / "unsound.py"
    src.write_text(UNSOUND_SRC, encoding="utf-8")
    obs = tmp_path / "obs.json"
    plan = tmp_path / "plan.json"
    r = _run("trace", str(src), "--entry", "unsound:main", "--out", str(obs), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    r = _run("plan", str(src), "--observations", str(obs), "--out", str(plan), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return src, obs, plan


def test_t1_open_hierarchy_callsite_must_not_be_rewritten(
    unsound_project: tuple[Path, Path, Path],
) -> None:
    """Animal has an unobserved subclass, so speak must not be rewritten."""
    _, _, plan_path = unsound_project
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    speak_plans = [
        p for p in payload["rewrite_plans"] if ".speak(" in p["replacement"]
    ]
    assert speak_plans == [], (
        "OPEN hierarchy speak callsite produced a rewrite plan: "
        + json.dumps(speak_plans, ensure_ascii=False)
    )


def test_t1_verdicts_are_per_method(
    unsound_project: tuple[Path, Path, Path],
) -> None:
    """Observations spanning run and speak must produce per-method verdicts."""
    _, _, plan_path = unsound_project
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    verdicts = payload["verdicts"]
    methods = {v["method_qualname"].rsplit(".", 1)[-1] for v in verdicts}
    assert {"run", "speak"} <= methods, (
        f"per-method verdict split failed: {[v['method_qualname'] for v in verdicts]}"
    )
    for v in verdicts:
        impls = {name.rsplit(".", 1)[-1] for name in v["known_impls"]}
        assert not ({"Worker"} & impls and {"Dog", "Cat"} & impls), (
            f"unrelated hierarchies merged in one verdict: {v['method_qualname']} -> "
            f"{sorted(impls)}"
        )


def test_t2_apply_with_entry_requires_cases(
    unsound_project: tuple[Path, Path, Path],
) -> None:
    """--apply --entry without --cases must be rejected as an ineffective gate."""
    src, _, plan_path = unsound_project
    out = src.parent / "rw.py"
    r = _run(
        "rewrite", str(src),
        "--plan", str(plan_path),
        "--out", str(out),
        "--apply", "--entry", "unsound:main",
        cwd=src.parent,
    )
    assert r.returncode != 0, (
        "--apply+--entry without cases succeeded; a single empty-case verification "
        f"is not a gate. stdout={r.stdout[:200]}"
    )


def test_t3_forged_plan_is_rejected(tmp_path: Path) -> None:
    """A source-hash-matching forged plan must not be trusted."""
    src = tmp_path / "victim.py"
    src.write_text(UNSOUND_SRC, encoding="utf-8")
    source = src.read_text(encoding="utf-8")
    forged = {
        "source_hash": hashlib.sha256(source.encode()).hexdigest(),
        "rewrite_plans": [
            {
                "replacement": "Dog.speak(pet)",
                "target_range": "27:8-27:19",
                "strategy": "direct",
                "verdict": {"status": "closed", "evidence": ["forged"]},
            }
        ],
    }
    plan_path = tmp_path / "forged.json"
    plan_path.write_text(json.dumps(forged), encoding="utf-8")
    out = tmp_path / "rw.py"
    r = _run(
        "rewrite", str(src),
        "--plan", str(plan_path),
        "--out", str(out),
        "--apply", "--skip-verify",
        cwd=tmp_path,
    )
    applied = out.exists() and "Dog.speak(pet)" in out.read_text(encoding="utf-8")
    assert r.returncode != 0 and not applied, (
        "forged plan was applied without revalidation"
    )


def test_t4_recursion_entry_callsite_is_observed(tmp_path: Path) -> None:
    """Regression guard: recursive entry callsite must be observed."""
    src = tmp_path / "recursion.py"
    src.write_text(
        textwrap.dedent(
            """
            from flatten.finals import final

            @final
            class Worker:
                def run(self, n):
                    if n <= 0:
                        return 0
                    return self.helper(n)
                def helper(self, n):
                    return Worker().run(n - 1) + n

            def main():
                return Worker().run(3)
            """
        ),
        encoding="utf-8",
    )
    obs = tmp_path / "obs.json"
    r = _run("trace", str(src), "--entry", "recursion:main", "--out", str(obs), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    records = json.loads(obs.read_text(encoding="utf-8"))
    entry_line = next(
        i + 1 for i, line in enumerate(src.read_text().splitlines())
        if "Worker().run(3)" in line
    )
    bound_lines = {rec["call_site_id"] for rec in records if rec["call_site_id"]}
    assert any(f":{entry_line}:" in site for site in bound_lines), (
        f"entry callsite line {entry_line} not observed. bound sites={sorted(bound_lines)}"
    )
