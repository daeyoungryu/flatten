# flatten Architecture

Last updated: 2026-06-11

## Module Flow

```text
source code
  -> discovery.py      finds obj.method(...) call sites with position ids
  -> observations.py   loads runtime/oracle records linked to call-site ids
  -> static.py         extracts class hierarchy and dynamic risk evidence
  -> closure.py        classifies CLOSED, OPEN, and UNSAFE dispatches
  -> planner.py        emits opt-in rewrite plans for CLOSED verdicts only
  -> transformer.py    applies exact PositionProvider-based LibCST rewrites
  -> harness.py        compares original and transformed behavior
```

Phase 0 safety hardening:

- `tracer.py` records caller file/line for dispatch observations.
- `cli.py` binds observations by recorded caller location, not method
  name/order guessing.
- `cli.py` restores observed `TypeRef` objects before invoking
  `ClosureChecker`; if restoration fails, the verdict is UNKNOWN and cannot
  rewrite.
- `cli.py` treats external plan files as untrusted unless source hash and
  serialized CLOSED evidence are present.

Phase 1 rewrite authorization:

- `contracts.py` defines `RewriteDecision` as the explicit allow/refuse record
  for rewrite authorization.
- `planner.py` computes decisions from closure verdicts before emitting plans.
- `cli.py` serializes `rewrite_decisions` in plan and dry-run rewrite output.

Phase 2 adversarial blocker expansion:

- `closure.py` treats dynamic attribute mutation hooks, subclass hooks, dynamic
  code execution, and dynamic imports as UNSAFE rewrite blockers.
- `static.py` reports the same blocker family in class `risk_flags`.

Phase 3 release artifacts:

- `docs/golden_corpus.md` records expected verdicts for representative examples.
- `docs/claim_test_map.md` links safety claims to test names.
- `.github/workflows/ci.yml` mirrors the local mandatory verification gate.

Post-phase call-site binding:

- `tracer.py` records caller bytecode column evidence when CPython exposes
  instruction positions.
- `cli.py` uses caller columns to bind same-line call sites instead of leaving
  them unbound.

Remaining implementation pass:

- `transformer.py` supports `guarded_temp` plans by inserting a temporary
  receiver assignment before a return statement.
- `closure.py` can consume a static class graph through `ClosureConfig`, and
  `cli.py` passes the analyzed graph in the planner path.

## Contracts

All shared records live in `src/flatten/contracts.py` to avoid circular imports:

- `OracleRecord`
- `CallSite`
- `ObservationRecord` plus `TypeRef` and `FunctionRef` in `observations.py`
- `ClosureVerdict`
- `TransformPlan`

## Dependency Boundaries

- `contracts.py` depends only on stdlib dataclasses/typing and LibCST types.
- `tracer.py`, `closure.py`, `discovery.py`, `observations.py`, `static.py`,
  `planner.py`, `transformer.py`, `collapse.py`, `dispatch.py`, and `harness.py` are
  independently importable.
- All code transformation is done with LibCST. `ast.unparse` is not used.
- Production rewrite targeting uses source positions, not structural
  `deep_equals` matching.

## Test Coverage

- Unit tests cover tracer, closure, collapse, dispatch, and harness.
- `tests/adversarial/test_phase0_defects.py` covers DEFECT-1 through DEFECT-6
  Phase 0 regressions.
- `tests/test_required_e2e.py` covers call-site discovery, closure safety,
  observation schema, position-based rewrite, and CLI integration.
- `tests/test_staff_contracts.py` covers structured observations, plan-file
  rewrite, and guarded receiver single-evaluation refusal.
- `tests/test_static_hierarchy.py` covers class graph extraction.
- Required local verification passes with 99 tests and 90.55% coverage.
