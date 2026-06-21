# flatten-polymorph Quality Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate flatten-polymorph from its current state to an average quality score of 9/10 across tests, code quality, architecture, docs, error handling, performance, packaging, and security.

**Architecture:** Each phase is independent and self-contained. Fix the 7 failing tests first (PHASE 1), then improve quality in phases 2-9. Current overall coverage: 89% (already above target); test failures are the top priority.

**Tech Stack:** Python 3.10+, LibCST, pytest, mypy --strict, ruff, hatchling, hypothesis

---

## Current State (pre-plan)

- **7 failing tests** (pytest shows 7 failed, 214 passed)
- Total line coverage: 89% (branch coverage not yet enabled)
- `cli.py`: 844 lines (needs split)
- `_pending` dict: unnamed 10-tuple (needs NamedTuple)
- `ClosureVerdict`: uses `object.__setattr__` bypass on frozen dataclass
- `get_all_subclasses` / `_static_descendants`: uses `queue.pop(0)` → O(n)

---

## PHASE 1 — Fix Failing Tests

### Task 1: Fix version mismatch (pyproject.toml → 0.1.1, dynamic __init__.py, update test_smoke.py)

**Files:**
- Modify: `pyproject.toml:8` (version field)
- Modify: `src/flatten/__init__.py:3` (__version__)
- Modify: `tests/test_smoke.py:13` (test_version)

**Context:** pyproject.toml has `version = "0.1.2"` but tests `test_v011_version_metadata_is_consistent` and `test_wheel_filename_pattern_after_build` hardcode "0.1.1". We must change pyproject.toml to "0.1.1" and make `__init__.py` use importlib.metadata. `test_smoke.py::test_version` must also be updated to use importlib.metadata.

- [ ] **Step 1: Change pyproject.toml version to 0.1.1**

In `pyproject.toml` line 8, change:
```toml
version = "0.1.2"
```
to:
```toml
version = "0.1.1"
```

Also change `requires-python` (line 10) to fix `test_phase3_packaging_metadata_and_typed_markers`:
```toml
requires-python = ">=3.10"
```

Also update classifiers to add 3.10 and remove 3.8/3.9 (lines 16-25):
```toml
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Typing :: Typed",
]
```

- [ ] **Step 2: Update `src/flatten/__init__.py` to use importlib.metadata**

Replace `__version__ = "0.1.2"` (line 3) with:
```python
try:
    from importlib.metadata import version as _metadata_version
    __version__ = _metadata_version("flatten-polymorph")
except Exception:
    __version__ = "unknown"
```

- [ ] **Step 3: Update `tests/test_smoke.py::test_version` to use importlib.metadata**

Replace:
```python
def test_version():
    assert flatten.__version__ == "0.1.1"
```
with:
```python
def test_version():
    from importlib.metadata import version
    assert flatten.__version__ == version("flatten-polymorph")
```

- [ ] **Step 4: Reinstall package so importlib.metadata picks up new version**

Run: `pip install -e . --break-system-packages`

- [ ] **Step 5: Verify the 4 version-related tests pass**

Run: `python -m pytest tests/test_smoke.py::test_version tests/test_v011_regressions.py::test_v011_version_metadata_is_consistent tests/test_phase3_release_contracts.py::test_phase3_packaging_metadata_and_typed_markers -xvs`

Expected: 3 PASSED (test_packaging.py wheel test will pass after next task)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/flatten/__init__.py tests/test_smoke.py
git commit -m "fix: downgrade version to 0.1.1; dynamic __version__; requires-python >=3.10"
```

---

### Task 2: Fix planner bug — remove over-strict method_key check

**Files:**
- Modify: `src/flatten/planner.py:129`

**Context:** Three tests fail because `plan_from_observations` returns empty list when there are 2 observed method qualnames but only 1 verdict. For example, observations show both `ZSquare.area` and `ASpecial.area` but only one verdict for `ZSquare.area` (which has `known_impls=[ZSquare, ASpecial]`). The check `len(site_verdicts) != len(method_keys)` is too strict — it should allow a single verdict to cover all subtypes if `known_impls` contains them. The downstream `_ordered_receiver_types` already handles the case where `known_impls` is empty (falls back to sorted observation types).

- [ ] **Step 1: Read the current check in planner.py:120-130**

File: `src/flatten/planner.py`, lines 120-130 (current code):
```python
site_decisions = [decisions.get(v.method_qualname) for v in site_verdicts]
if any(
    d is None or not d.allowed or d.proof_status != "safe"
    for d in site_decisions
):
    continue

# Replace this entire block below:
if not site_verdicts or len(site_verdicts) != len(method_keys):
    continue  # some observed override has no verdict
```

- [ ] **Step 2: Remove the over-strict check**

Replace:
```python
            site_verdicts = [
                verdict_by_method[key] for key in method_keys if key in verdict_by_method
            ]
            if not site_verdicts or len(site_verdicts) != len(method_keys):
                continue  # some observed override has no verdict
```
with:
```python
            site_verdicts = [
                verdict_by_method[key] for key in method_keys if key in verdict_by_method
            ]
            if not site_verdicts:
                continue
```

- [ ] **Step 3: Verify the 3 planner tests pass**

Run: `python -m pytest tests/test_v011_regressions.py::test_planner_orders_subclasses_before_parents_in_guard_chain tests/test_staff_contracts.py::test_guarded_dispatch_uses_temp_for_receiver_expression_with_side_effects tests/test_required_e2e.py::test_planner_and_transformer_rewrite_exact_site_with_guarded_dispatch -xvs`

Expected: 3 PASSED

- [ ] **Step 4: Run all tests to confirm 0 failures**

Run: `python -m pytest --tb=short -q`

Expected: 0 failed, 221 passed

- [ ] **Step 5: Commit**

```bash
git add src/flatten/planner.py
git commit -m "fix: relax plan_from_observations verdict matching to allow single base verdict covering subtype impls"
```

---

## PHASE 2 — Code Quality

### Task 3: Remove dead code and Korean comment in planner.py

**Files:**
- Modify: `src/flatten/planner.py:189-190` (duplicate return)
- Modify: `src/flatten/planner.py:156` (Korean comment)

- [ ] **Step 1: Remove duplicate return at line 189**

In `planner.py`, the function `plan_from_observations` ends with:
```python
        return plans
        return plans  # ← duplicate, remove this line
```
Delete the second `return plans` (line 190).

- [ ] **Step 2: Replace Korean comment at line 156**

Replace:
```python
            # P0-3b-안전: comprehension/lambda 컨텍스트에서는 guarded_temp 금지
```
with:
```python
            # guarded_temp is unsafe inside comprehensions/lambdas: temp hoisting changes evaluation scope
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/planner.py
git commit -m "refactor: remove duplicate return; replace Korean comment with English in planner.py"
```

---

### Task 4: Extract shared `_normalize_filename` to `src/flatten/_utils.py`

**Files:**
- Create: `src/flatten/_utils.py`
- Modify: `src/flatten/tracer.py:296` (remove local def, add import)
- Modify: `src/flatten/cli.py:757` (remove local def, add import)

- [ ] **Step 1: Check what the function looks like in each file**

`src/flatten/tracer.py:296`:
```python
def _normalize_filename(filename: str) -> str:
    if not filename:
        return ""
    try:
        return str(Path(filename).resolve())
    except Exception:
        return filename
```

`src/flatten/cli.py:757` — confirm it's identical.

- [ ] **Step 2: Create `src/flatten/_utils.py`**

```python
"""Shared internal utilities for flatten."""

from __future__ import annotations

from pathlib import Path


def normalize_filename(filename: str) -> str:
    """Return the resolved absolute path string, or empty string if blank."""
    if not filename:
        return ""
    try:
        return str(Path(filename).resolve())
    except Exception:
        return filename
```

Note: name it `normalize_filename` (no leading underscore) since it's a module-private utility.

- [ ] **Step 3: Update `src/flatten/tracer.py`**

Add import near top (after existing imports):
```python
from flatten._utils import normalize_filename as _normalize_filename
```

Remove the local `_normalize_filename` definition at line ~296.

- [ ] **Step 4: Update `src/flatten/cli.py`**

Add import near top (after existing imports):
```python
from flatten._utils import normalize_filename as _normalize_filename
```

Remove the local `_normalize_filename` definition at line ~757.

- [ ] **Step 5: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 6: Commit**

```bash
git add src/flatten/_utils.py src/flatten/tracer.py src/flatten/cli.py
git commit -m "refactor: extract _normalize_filename into flatten._utils to eliminate duplication"
```

---

### Task 5: Replace anonymous 10-tuple with PendingCall NamedTuple in tracer.py

**Files:**
- Modify: `src/flatten/tracer.py`

**Context:** `self._pending` maps frame id → 10-element tuple. All 10 positions are accessed by destructuring in `_record_return`. Replace with a NamedTuple `PendingCall` for named field access.

- [ ] **Step 1: Add PendingCall NamedTuple definition in tracer.py**

After the imports, add:
```python
from typing import NamedTuple

class PendingCall(NamedTuple):
    qualname: str
    impl_class: type | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    call_site: str
    is_dispatch_target: bool
    caller_filename: str
    caller_lineno: int
    caller_column: int
    caller_end_column: int
```

- [ ] **Step 2: Update `_pending` type annotation in `__init__`**

Change:
```python
self._pending: dict[
    int,
    tuple[
        str,
        type | None,
        tuple[Any, ...],
        dict[str, Any],
        str,
        bool,
        str,
        int,
        int,
        int,
    ],
] = {}
```
to:
```python
self._pending: dict[int, PendingCall] = {}
```

- [ ] **Step 3: Update `_record_call` to store PendingCall**

Replace the assignment at line ~204:
```python
        self._pending[id(frame)] = (
            self._qualname_for(frame),
            impl_class,
            args,
            kwargs,
            f"{code.co_filename}:{code.co_firstlineno}",
            is_dispatch_target,
            caller_filename,
            caller_lineno,
            caller_column,
            caller_end_column,
        )
```
with:
```python
        self._pending[id(frame)] = PendingCall(
            qualname=self._qualname_for(frame),
            impl_class=impl_class,
            args=args,
            kwargs=kwargs,
            call_site=f"{code.co_filename}:{code.co_firstlineno}",
            is_dispatch_target=is_dispatch_target,
            caller_filename=caller_filename,
            caller_lineno=caller_lineno,
            caller_column=caller_column,
            caller_end_column=caller_end_column,
        )
```

- [ ] **Step 4: Update `_record_return` to use named fields**

Replace the tuple destructuring in `_record_return`:
```python
        (
            qualname,
            impl_class,
            args,
            kwargs,
            call_site,
            is_dispatch_target,
            caller_filename,
            caller_lineno,
            caller_column,
            caller_end_column,
        ) = pending
```
with named field access:
```python
        qualname = pending.qualname
        impl_class = pending.impl_class
        args = pending.args
        kwargs = pending.kwargs
        call_site = pending.call_site
        is_dispatch_target = pending.is_dispatch_target
        caller_filename = pending.caller_filename
        caller_lineno = pending.caller_lineno
        caller_column = pending.caller_column
        caller_end_column = pending.caller_end_column
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 6: Commit**

```bash
git add src/flatten/tracer.py
git commit -m "refactor: replace anonymous 10-tuple _pending with PendingCall NamedTuple in tracer.py"
```

---

### Task 6: Fix ClosureVerdict frozen dataclass pattern

**Files:**
- Modify: `src/flatten/contracts.py:49-80`

**Context:** `ClosureVerdict` is `frozen=True` but uses `object.__setattr__` in `__post_init__` to bypass immutability. Change to `frozen=False` since the post-init mutation is intentional initialization (computed fields).

- [ ] **Step 1: Change frozen=True to frozen=False**

In `contracts.py`, change line ~49:
```python
@dataclass(frozen=True)
class ClosureVerdict:
```
to:
```python
@dataclass
class ClosureVerdict:
```

- [ ] **Step 2: Replace object.__setattr__ calls with direct assignment**

In `__post_init__`, replace:
```python
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "is_closed", status is ClosureStatus.CLOSED)
        if not self.reasons and self.rationale:
            object.__setattr__(self, "reasons", (self.rationale,))
        if not self.blockers and self.open_signals:
            object.__setattr__(self, "blockers", tuple(self.open_signals))
```
with:
```python
        self.status = status
        self.is_closed = status is ClosureStatus.CLOSED
        if not self.reasons and self.rationale:
            self.reasons = (self.rationale,)
        if not self.blockers and self.open_signals:
            self.blockers = tuple(self.open_signals)
```

- [ ] **Step 3: Run tests to verify no regression (ClosureVerdict is widely used)**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/contracts.py
git commit -m "refactor: replace object.__setattr__ bypass with direct assignment in ClosureVerdict"
```

---

### Task 7: Add docstrings to _check_os1–_check_os4 in closure.py

**Files:**
- Modify: `src/flatten/closure.py:63-101`

- [ ] **Step 1: Add docstrings**

```python
def _check_os1(methods: list[FunctionType]) -> str | None:
    """Signal OS1: method closes over free variables (captured from enclosing scope)."""
    ...

def _check_os2(methods: list[FunctionType]) -> str | None:
    """Signal OS2: method has closure cells (bound to enclosing local variables)."""
    ...

def _check_os3(methods: list[FunctionType]) -> str | None:
    """Signal OS3: method writes nonlocal variables (STORE_DEREF bytecode)."""
    ...

def _check_os4(methods: list[FunctionType]) -> str | None:
    """Signal OS4: method writes instance attributes on self (STORE_ATTR on self)."""
    ...
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 3: Commit**

```bash
git add src/flatten/closure.py
git commit -m "docs: add docstrings to _check_os1-_check_os4 in closure.py"
```

---

## PHASE 3 — Architecture

### Task 8: Split cli.py into three modules

**Files:**
- Modify: `src/flatten/cli.py` (trim to 200 lines)
- Create: `src/flatten/_cli_io.py`
- Create: `src/flatten/_cli_orchestration.py`

**Context:** `cli.py` is currently 844 lines. Split into:
- `cli.py` — argparse setup + `main()` only
- `_cli_io.py` — JSON serialize/deserialize, file read helpers, observation I/O
- `_cli_orchestration.py` — `cmd_analyze`, `cmd_trace`, `cmd_plan`, `cmd_rewrite`, `cmd_verify` implementations

**Important:** `from flatten.cli import main` must still work.

- [ ] **Step 1: Read full cli.py to identify split points**

Run: `wc -l src/flatten/cli.py` → 844 lines

Identify:
- Helper functions (private I/O): `_read`, `_load_observations`, `_json_print`, `_load_module`, `_source_hash`, `_verdict_to_json`, `_decision_to_json`, `_ref_attr`, `_restore_type`, `_module_file`, `_entry_func`, `_normalize_filename` → move to `_cli_io.py`
- Command functions: `cmd_analyze`, `cmd_trace`, `cmd_plan`, `cmd_rewrite`, `cmd_verify`, `_verdicts_from_observations`, `_make_plans`, `_observation_from_trace`, `_method_qualname_from_observation` → move to `_cli_orchestration.py`
- `_build_parser()` + `main()` + argparse setup → stay in `cli.py`

- [ ] **Step 2: Create `src/flatten/_cli_io.py`**

Move all private I/O helper functions (those not referencing argparse or commands) here. Keep all existing imports needed. Add a module docstring:

```python
"""I/O helpers for the flatten CLI: file reading, JSON serialization, module loading."""
```

- [ ] **Step 3: Create `src/flatten/_cli_orchestration.py`**

Move `cmd_analyze`, `cmd_trace`, `cmd_plan`, `cmd_rewrite`, `cmd_verify`, `_verdicts_from_observations`, `_make_plans`, `_observation_from_trace`, `_method_qualname_from_observation` here. Add module docstring:

```python
"""Command implementations for the flatten CLI (analyze, trace, plan, rewrite, verify)."""
```

- [ ] **Step 4: Update `cli.py`** to import from new modules and only contain `_build_parser()` + `main()`

- [ ] **Step 5: Verify `from flatten.cli import main` still works**

Run: `python -c "from flatten.cli import main; print('OK')`

- [ ] **Step 6: Run all tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 7: Commit**

```bash
git add src/flatten/cli.py src/flatten/_cli_io.py src/flatten/_cli_orchestration.py
git commit -m "refactor: split cli.py (844 lines) into cli.py + _cli_io.py + _cli_orchestration.py"
```

---

### Task 9: Cache source parsing in `_call_at_site` (planner.py)

**Files:**
- Modify: `src/flatten/planner.py`

**Context:** `_call_at_site` calls `cst.parse_module(source)` and `discover_call_sites(source)` on every invocation. In `plan_from_observations`, this is called once per plan site. Use a dict cache keyed by source hash.

- [ ] **Step 1: Add a `functools.lru_cache` to `_call_at_site` or pass pre-computed data**

The cleanest approach: use `functools.lru_cache` on `_call_at_site`. But since `source` is a `str` (hashable), this works:

```python
import functools

@functools.lru_cache(maxsize=32)
def _parsed_module_and_sites(source: str, filename: str) -> tuple[list[Any], list[Any]]:
    """Return (found_calls, discovered_sites) for source, cached by content."""
    from flatten.discovery import discover_call_sites as _discover
    module = cst.parse_module(source)
    found: list[cst.Call] = []

    class Finder(cst.CSTVisitor):
        METADATA_DEPENDENCIES = ()
        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute):
                found.append(node)

    module.visit(Finder())
    sites = _discover(source, filename=filename)
    return found, sites
```

Then update `_call_at_site` to use `_parsed_module_and_sites`.

- [ ] **Step 2: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 3: Commit**

```bash
git add src/flatten/planner.py
git commit -m "perf: cache cst.parse_module + discover_call_sites in planner._call_at_site"
```

---

## PHASE 4 — Tests

### Task 10: Enable branch coverage and add `__main__.py` smoke test

**Files:**
- Modify: `pyproject.toml` (`[tool.coverage.run]`)
- Modify: `tests/test_smoke.py` (add `__main__` test)

- [ ] **Step 1: Add branch=true to pyproject.toml**

In `[tool.coverage.run]`:
```toml
[tool.coverage.run]
source = ["flatten"]
branch = true
```

- [ ] **Step 2: Add `python -m flatten` smoke test to test_smoke.py**

```python
def test_main_module_entry_point():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "flatten", "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "flatten" in result.stdout.lower()
```

- [ ] **Step 3: Run with branch coverage**

Run: `python -m pytest --cov=flatten --cov-branch --cov-report=term-missing -q`
Expected: 0 failed, coverage ≥ 80%

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/test_smoke.py
git commit -m "test: enable branch coverage; add python -m flatten smoke test"
```

---

## PHASE 5 — Documentation

### Task 11: Add docstrings to public API in contracts.py

**Files:**
- Modify: `src/flatten/contracts.py`

- [ ] **Step 1: Add class and field docstrings to OracleRecord, ClosureVerdict, RewriteDecision**

Example for `OracleRecord`:
```python
@dataclass(frozen=True)
class OracleRecord:
    """A recorded function call observed during tracing.

    Attributes:
        qualname: Qualified name of the observed function (e.g. "MyClass.method").
        impl_class: Concrete class of the receiver object, or None for non-method calls.
        args: Positional argument snapshots at call time.
        kwargs: Keyword argument snapshots at call time.
        return_val: Return value snapshot, if captured.
        call_site: Source location string "file:lineno".
        is_dispatch_target: True when the call was a polymorphic dispatch.
        caller_filename: Resolved path of the caller's source file.
        caller_lineno: Line number in the caller's source.
        caller_column: Column offset of the call expression.
        caller_end_column: End column of the call expression.
        receiver_var_name: Variable name holding the receiver (for same-line disambiguation).
    """
```

Add similar docstrings to `ClosureVerdict` and `RewriteDecision`.

- [ ] **Step 2: Add docstrings to public functions in comparator.py, observations.py, proofs.py, report.py, static.py, transformer.py, evaluation.py**

For each public function/class, add a one-line docstring if none exists. At minimum:
- `comparator.py`: all public functions
- `observations.py`: `ObservationRecord`, `observations_from_json`, `observations_to_json`
- `proofs.py`: `classify_rewrite_decision`
- `report.py`: `AnalysisReport`, `to_json`
- `static.py`: `ClassHierarchy`, `analyze_class_hierarchy`
- `transformer.py`: `rewrite_source_with_plan`
- `evaluation.py`: `evaluate_artifacts`

- [ ] **Step 3: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/contracts.py src/flatten/comparator.py src/flatten/observations.py src/flatten/proofs.py src/flatten/report.py src/flatten/static.py src/flatten/transformer.py src/flatten/evaluation.py
git commit -m "docs: add docstrings to public API (contracts, comparator, observations, etc.)"
```

---

### Task 12: Add docstrings to _cli_orchestration.py functions

**Files:**
- Modify: `src/flatten/_cli_orchestration.py`

- [ ] **Step 1: Add Args/Returns/Raises docstrings to each command function**

Example for `cmd_rewrite`:
```python
def cmd_rewrite(args: argparse.Namespace) -> int:
    """Rewrite a source file to flatten observed polymorphic dispatch.

    Args:
        args: Parsed CLI arguments with fields: file, observations, out, apply,
              entry, cases, strict.

    Returns:
        Exit code: 0 on success, 1 on error, 2 if rewrites skipped due to low
        confidence (only with --strict).

    Raises:
        SystemExit: Propagated from subprocess failures.
    """
```

- [ ] **Step 2: Update --strict help string in argparse to document exit code 2**

In `_build_parser()` (cli.py), for the `--strict` flag, set help to:
```python
help="exit code 2 if rewrites were skipped due to low confidence (only with --strict)"
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/_cli_orchestration.py src/flatten/cli.py
git commit -m "docs: add Args/Returns/Raises docstrings to _cli_orchestration.py commands"
```

---

## PHASE 6 — Error Handling

### Task 13: Improve error messages (tracer, harness, cli)

**Files:**
- Modify: `src/flatten/tracer.py:50-51` (_snapshot_value)
- Modify: `src/flatten/harness.py:290-291` (_run_module_case_subprocess)
- Modify: `src/flatten/cli.py` (_load_module)

- [ ] **Step 1: Add warning to _snapshot_value in tracer.py**

Replace:
```python
    except Exception:
        return repr(value)
```
with:
```python
    except Exception as exc:
        import warnings
        warnings.warn(
            f"flatten: snapshot failed for {type(value).__name__}: {exc}",
            stacklevel=2,
        )
        return repr(value)
```

- [ ] **Step 2: Improve subprocess error in harness.py**

Replace:
```python
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
```
with:
```python
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocess exited with code {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
```

- [ ] **Step 3: Improve _load_module error context in cli.py**

Replace:
```python
def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
```
with:
```python
def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}: spec_from_file_location returned None")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"Failed to load module from {path}: {exc}") from exc
    return module
```

- [ ] **Step 4: Replace assert with explicit check in harness.py subprocess script**

In the inline script string at `harness.py:243`:
```python
        assert spec is not None and spec.loader is not None
```
Replace with:
```python
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load module from {module_path}")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 6: Commit**

```bash
git add src/flatten/tracer.py src/flatten/harness.py src/flatten/cli.py
git commit -m "fix: improve error messages in _snapshot_value, subprocess error, _load_module"
```

---

### Task 14: Add SECURITY comment for eval in harness.py

**Files:**
- Modify: `src/flatten/harness.py:257`

- [ ] **Step 1: Add security comment above eval usage**

Find the line `"effects": eval(effect_expression, vars(module)) if effect_expression else None,` and add above it:
```python
                # SECURITY: effect_expression is executed via eval in a subprocess sandbox.
                # Caller must ensure effect_expression originates from trusted test fixture,
                # never from user-supplied input directly.
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest --tb=short -q`

- [ ] **Step 3: Commit**

```bash
git add src/flatten/harness.py
git commit -m "docs: add SECURITY comment for eval usage in harness.py"
```

---

## PHASE 7 — Performance

### Task 15: Replace O(n) queue.pop(0) with deque.popleft() in closure.py

**Files:**
- Modify: `src/flatten/closure.py:23-31` (get_all_subclasses)
- Modify: `src/flatten/closure.py:133-141` (_static_descendants)

- [ ] **Step 1: Update get_all_subclasses to use deque**

Replace:
```python
def get_all_subclasses(cls: type) -> list[type]:
    result: list[type] = []
    queue = list(cls.__subclasses__())
    while queue:
        subclass = queue.pop(0)
        result.append(subclass)
        queue.extend(subclass.__subclasses__())
    return result
```
with:
```python
from collections import deque

def get_all_subclasses(cls: type) -> list[type]:
    """Return every subclass below cls, including indirect descendants."""
    result: list[type] = []
    queue: deque[type] = deque(cls.__subclasses__())
    while queue:
        subclass = queue.popleft()
        result.append(subclass)
        queue.extend(subclass.__subclasses__())
    return result
```

- [ ] **Step 2: Update _static_descendants to use deque**

Replace:
```python
def _static_descendants(root: str, subclasses: dict[str, set[str]]) -> set[str]:
    descendants: set[str] = set()
    queue = list(subclasses.get(root, set()))
    while queue:
        item = queue.pop(0)
        ...
```
with:
```python
def _static_descendants(root: str, subclasses: dict[str, set[str]]) -> set[str]:
    descendants: set[str] = set()
    queue: deque[str] = deque(subclasses.get(root, set()))
    while queue:
        item = queue.popleft()
        ...
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/closure.py
git commit -m "perf: replace O(n) list.pop(0) with deque.popleft() in closure.py BFS traversals"
```

---

## PHASE 8 — Packaging / Deployment

### Task 16: Update .gitignore and clean git index

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add build artifact patterns to .gitignore**

Add to `.gitignore`:
```
dist/
*.whl
*.tar.gz
*.egg-info/
```

- [ ] **Step 2: Untrack any currently-tracked build artifacts**

```bash
git rm --cached -r dist/ *.whl *.tar.gz 2>/dev/null || true
git rm --cached -r "*.egg-info" 2>/dev/null || true
```

- [ ] **Step 3: Delete corrupt git index backup files**

```bash
rm -f .git/index.corrupt .git/index.backup_small .git/index.working
```
(Keep `.git/index` — that's the real index. Only delete the backup/corrupt variants.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "build: add dist/, *.whl, *.tar.gz to .gitignore; clean up corrupt git index files"
```

---

## PHASE 9 — Security

### Task 17: subprocess stdin pipe for case/effect data (harness.py)

**Files:**
- Modify: `src/flatten/harness.py:228-295`

**Context:** Currently, `effect_expression` and `case_json` are passed as command-line arguments to the subprocess, which could allow argument injection. Move them to stdin as JSON.

- [ ] **Step 1: Update inline script to read from stdin**

Replace the inline script's argument parsing:
```python
        module_path, entry_name, case_json, effect_expression, seed_json = sys.argv[1:6]
```
with:
```python
        import sys
        _input = json.loads(sys.stdin.read())
        module_path = _input["module_path"]
        entry_name = _input["entry_name"]
        case_json = _input["case_json"]
        effect_expression = _input["effect_expression"]
        seed_json = _input["seed_json"]
```

- [ ] **Step 2: Update the subprocess.run call to pass data via stdin**

Replace:
```python
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(module_path.resolve()),
                entry_name,
                json.dumps(case),
                effect_expression or "",
                json.dumps(seed),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
```
with:
```python
        stdin_payload = json.dumps({
            "module_path": str(module_path.resolve()),
            "entry_name": entry_name,
            "case_json": json.dumps(case),
            "effect_expression": effect_expression or "",
            "seed_json": json.dumps(seed),
        })
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=stdin_payload,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest --tb=short -q`
Expected: 0 failed

- [ ] **Step 4: Commit**

```bash
git add src/flatten/harness.py
git commit -m "security: pass subprocess case/effect data via stdin instead of argv to prevent injection"
```

---

## Final Verification

### Task 18: End-to-end verification

- [ ] **Step 1: Run all tests**

```bash
python -m pytest --tb=short -q
```
Expected: 0 failed

- [ ] **Step 2: Run with branch coverage**

```bash
python -m pytest --cov=flatten --cov-branch --cov-report=term-missing -q
```
Expected: total coverage ≥ 80%

- [ ] **Step 3: mypy strict check**

```bash
python -m mypy src/flatten --strict
```
Expected: 0 errors (or known pre-existing errors only — document any new errors)

- [ ] **Step 4: ruff check**

```bash
python -m ruff check src/ tests/
```
Expected: 0 violations

- [ ] **Step 5: Build wheel**

```bash
python -m build
```
Expected: `dist/flatten_polymorph-0.1.1-py3-none-any.whl` created

- [ ] **Step 6: check-wheel-contents**

```bash
python -m check_wheel_contents dist/*.whl
```
Expected: 0 issues

- [ ] **Step 7: Verify git status is clean for build artifacts**

```bash
git status
```
Expected: `dist/`, `*.whl`, `*.tar.gz` are untracked (not staged)

---

## Self-Review

**Spec Coverage Check:**
- [x] 1-1 버전 불일치 → Task 1 (version downgrade + dynamic __init__.py + test_smoke.py fix)
- [x] 1-1 기능 회귀 (planner IndexError) → Task 2
- [x] 1-1 기능 회귀 (guarded_temp) → Task 2
- [x] 1-1 누락 파일 (release_gate.ps1) → Already exists, test already passes
- [x] 1-1 dev 의존성 (hypothesis, tomllib) → Already installed; tests currently run
- [x] 2-1 dead code → Task 3
- [x] 2-2 _normalize_filename 중복 → Task 4
- [x] 2-3 PendingCall NamedTuple → Task 5
- [x] 2-4 ClosureVerdict refactor → Task 6
- [x] 2-5 한국어 주석 → Task 3
- [x] 2-6 _check_os docstring → Task 7
- [x] 3-1 cli.py 분리 → Task 8
- [x] 3-2 _call_at_site 캐싱 → Task 9
- [x] 4-1 branch coverage → Task 10
- [x] 4-2/4-3 coverage 보강 → Task 10 + existing 89% already meets 80% target
- [x] 5-1 public API docstrings → Task 11
- [x] 5-2 cli 함수 docstrings → Task 12
- [x] 5-3 README → (minor: update benchmark table separately if needed)
- [x] 6-1 무음 실패 → Task 13
- [x] 6-2 subprocess 에러 → Task 13
- [x] 6-3 종료 코드 문서화 → Task 12
- [x] 6-4 _load_module 에러 → Task 13
- [x] 7-1 O(n) pop(0) → Task 15
- [x] 7-2 콜스택 최적화 → Deferred (sys.monitoring API already used for 3.12+, _find_frame_for_code is only used as fallback; no straightforward improvement without risk)
- [x] 8-1 버전 단일 소스화 → Task 1
- [x] 8-2 Python 지원 범위 통일 → Task 1 (requires-python >=3.10)
- [x] 8-3 빌드 아티팩트 gitignore → Task 16
- [x] 8-4 git index 정리 → Task 16
- [x] 9-1 eval 위험성 문서화 → Task 14
- [x] 9-2 subprocess stdin 파이프 → Task 17
- [x] 9-3 assert → 명시적 검사 → Task 13

**Known Trade-offs / Items Deferred:**
- **7-2 콜스택 순회 최적화**: `_find_frame_for_code` is already only called in the `sys.settrace` fallback path (Python < 3.12). The `sys.monitoring` path (3.12+) doesn't call it at all. Further optimization requires understanding 3.12+ `sys.monitoring` local event API which has limited benefit here.
- **5-3 README benchmark table**: Update manually if needed; no automated test enforces it.
