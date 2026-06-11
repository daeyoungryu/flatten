# flatten Project Summary

Last updated: 2026-06-11

## Overview

`flatten-polymorph` is a Python package for flattening observed polymorphic
dispatch into direct calls or guarded LibCST expressions when the dispatch can
be treated as closed. The implementation package remains `flatten`, with a
`flatten_polymorph` import alias for the distribution name.

## Current Status

Implemented:

- Data contracts are frozen in `src/flatten/contracts.py`.
- Static call-site discovery records position-based `CallSite` identifiers.
- Observation JSON records link a call-site id to concrete `TypeRef` receiver
  identities and `FunctionRef` resolved functions. Legacy string observations
  still parse for compatibility but are not the preferred safety contract.
- Static AST hierarchy extraction records classes, bases, methods, final
  decorators, subclass edges, method override sets, and dynamic risk flags.
- Runtime tracing records `OracleRecord` values with qualname, implementation
  class, positional args, keyword-only args, and return value.
- Python version split uses `sys.version_info >= (3, 12)`.
- Closure analysis exposes OS1-OS5 signals, CLOSED verdicts for final/sealed
  cases, and UNSAFE verdicts for dynamic dispatch hazards.
- Collapse transformation applies `TransformPlan` batches with LibCST.
- Dispatch generation supports direct calls and multiple-implementation
  `isinstance` expressions.
- Position-based transformer rewrites only the exact call site selected by the
  plan.
- Harness compares return values, exception type/message, stdout, stderr, and
  optional collected effects.
- Tests cover A1-A6 including an end-to-end polymorphic pipeline.
- CLI now supports analyze, trace, plan, rewrite, verify, and report commands,
  including plan-file based rewrite.

Phase 0 hardening verified:

- CLI planning no longer auto-promotes observed receiver types into
  `sealed_roots`; it restores observed type objects and refuses CLOSED when
  restoration fails.
- `rewrite` defaults to dry-run and writes only with explicit `--apply`.
- Runtime observations carry caller frame file/line evidence; unbound
  observations are excluded from rewrite planning and counted in plan output.
- OS4 blocks instance attribute writes, not reads; `@final` methods that only
  read `self.attr` can still be CLOSED.
- External plan files require a matching source hash plus serialized CLOSED
  verdict evidence.
- `verify` accepts `--cases` and reports minimal verification coverage for a
  single case.

Phase 1 rewrite-decision contract verified:

- `RewriteDecision` is the explicit rewrite authorization record derived from
  `ClosureVerdict.status`, confidence, blockers, reasons, and evidence.
- `RewritePlanner.decide()` exposes allow/refuse decisions separately from
  emitted `TransformPlan` values.
- CLI plan and rewrite dry-run output include `rewrite_decisions`, so refused
  rewrites are visible even when `rewrite_plans` is empty.
- Type restoration reloads the fallback source module when a stale same-name
  module is already present in `sys.modules`.

Phase 2 adversarial blockers verified:

- Closure analysis marks custom `__setattr__`, `__delattr__`, and
  `__init_subclass__` hooks as UNSAFE.
- Closure analysis marks observed methods that execute dynamic code
  (`eval`, `exec`, `__import__`) or perform imports as UNSAFE.
- Static hierarchy reporting emits matching risk flags for Phase 2 dynamic
  blockers.

Phase 3 release-readiness verified:

- `docs/golden_corpus.md` defines the safe/unsafe/review corpus.
- `docs/claim_test_map.md` maps public claims to executable tests.
- CI runs import smoke, pytest, coverage, ruff, and mypy gates.
- README documents `RewriteDecision` and Phase 2 blockers.

Post-phase call-site binding fix:

- Runtime tracing records caller source columns from bytecode positions when
  available.
- CLI observation binding uses caller line and column to disambiguate multiple
  method calls on the same source line.

Remaining implementation pass:

- Guarded dispatch for non-name receivers now emits a statement-level temporary
  receiver in return statements, avoiding repeated receiver evaluation.
- CLI planner closure evidence uses the static class graph for local hierarchy
  closure instead of runtime `__subclasses__` evidence.

## Verification

Use:

```powershell
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -c "import flatten"
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m pytest -q
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m pytest --cov=flatten --cov-report=term-missing --cov-fail-under=90
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m ruff check .
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m mypy .
```

Current result: all required local verification commands pass. Coverage gate
reports 90.55%, and the regression suite reports 99 passed.

External blockers: hosted GitHub Actions requires access to GitHub Actions or
an installed/authenticated `gh` CLI; mutation testing requires Linux/WSL because
native Windows is unsupported by `mutmut`.
