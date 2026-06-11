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

Phase 0 safety hardening: ✅ COMPLETED

- `tracer.py` records caller file/line for dispatch observations.
- `cli.py` binds observations by recorded caller location, not method
  name/order guessing.
- `cli.py` restores observed `TypeRef` objects before invoking
  `ClosureChecker`; if restoration fails, the verdict is UNKNOWN and cannot
  rewrite.
- `cli.py` treats external plan files as untrusted unless source hash and
  serialized CLOSED evidence are present.

Phase 1 rewrite authorization: ✅ COMPLETED

- `contracts.py` defines `RewriteDecision` as the explicit allow/refuse record
  for rewrite authorization.
- `planner.py` computes decisions from closure verdicts before emitting plans.
- `cli.py` serializes `rewrite_decisions` in plan and dry-run rewrite output.

Phase 2 adversarial blocker expansion: ✅ COMPLETED

- `closure.py` treats dynamic attribute mutation hooks, subclass hooks, dynamic
  code execution, and dynamic imports as UNSAFE rewrite blockers.
- `static.py` reports the same blocker family in class `risk_flags`.

Phase 3 release artifacts: ✅ COMPLETED

- `docs/golden_corpus.md` records expected verdicts for representative examples.
- `docs/claim_test_map.md` links safety claims to test names.
- `.github/workflows/ci.yml` mirrors the local mandatory verification gate.

Post-phase call-site binding: ✅ COMPLETED

- `tracer.py` records caller bytecode column evidence when CPython exposes
  instruction positions.
- `cli.py` uses caller columns to bind same-line call sites instead of leaving
  them unbound.

Remaining implementation pass: ✅ COMPLETED

- `transformer.py` supports `guarded_temp` plans by inserting a temporary
  receiver assignment before a return statement.
- `closure.py` can consume a static class graph through `ClosureConfig`, and
  `cli.py` passes the analyzed graph in the planner path.

External Phase 1 defect pass: COMPLETED

- `closure.py` uses the method declaration owner, not the observed concrete
  implementation owner, as the closure basis. CLOSED now requires positive
  final, sealed allowlist, or closed-world evidence.
- `discovery.py`, `tracer.py`, `observations.py`, and `cli.py` normalize path
  boundaries so relative CLI invocations bind observations to call sites.
- `planner.py` preserves every `TransformPlan` field when authorizing plans.
- CLI plan output warns on unbound observations that produce zero plans, and
  `--strict` turns that warning into a non-zero exit.

External Phase 2 safety pass: COMPLETED

- `contracts.py` expands `RewriteDecision` into the structured safety decision
  record used for allowed and refused rewrites.
- `planner.py` can construct per-callsite decision metadata for planned
  rewrites.
- `harness.py` adds subprocess-isolated module verification with stdout,
  stderr, return/exception, side-effect, seed, and timeout handling.
- `docs/REWRITE_POLICY.md` and `docs/SAFETY_MODEL.md` document reason codes,
  conservative refusal, and the epistemic limit of observed-input verification.

External Phase 3 release pass: COMPLETED

- Packaging includes typed markers, metadata classifiers, console script, and a
  compatibility shim for `flatten_polymorph`.
- CI is split into lint, typecheck, test, build, wheel-install-smoke, and
  cli-smoke jobs over Windows/Ubuntu and Python 3.10/3.12.
- Documentation now includes architecture, safety model, rewrite policy,
  unsupported cases, testing strategy, CLI, examples, roadmap, and report schema.
- Examples are runnable scripts for allowed and rejected policy outcomes.

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
- `tests/test_soundness_unobserved_sibling.py`,
  `tests/test_confidence_contract.py`, `tests/test_relative_path_binding.py`,
  and `tests/test_planner_field_preservation.py` cover Phase 1 D1-D4.
- `tests/test_phase2_rewrite_decisions.py`,
  `tests/test_phase2_harness_subprocess.py`,
  `tests/test_phase2_negative_mutations.py`, `tests/test_fuzz_safety.py`, and
  `tests/differential/` cover Phase 2 safety decisions, harness isolation,
  mutation-like branch protection, fuzz rejection, and 20 differential cases.
- `tests/test_phase3_release_contracts.py` covers Phase 3 docs, schema,
  packaging metadata, typed markers, guarded entry points, CI, and examples.
- Required Phase 3 local verification passes with 174 tests.

## v0.1.1 Architecture Update

- `ClosureChecker` can return `PROBABLY_CLOSED`; `RewriteDecision` treats it as
  a refusal with `OPEN_CLOSURE_INCOMPLETE`.
- Guarded rewrite expressions preserve behavior for unexpected receiver types
  by ending in the original dynamic dispatch expression.
- CLI tracing defaults to metadata-only capture; deep value capture is opt-in
  with `--capture-values`.
- `scripts/release_gate.ps1` verifies the built wheel in a clean venv, including
  installed-package compileall, module help, strict mypy, and a minimal e2e.
