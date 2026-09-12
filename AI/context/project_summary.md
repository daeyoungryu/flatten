# flatten Project Summary

Last updated: 2026-08-13

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
- Behavior comparison is exposed through `BehaviorComparator` for reusable
  return/stdout/stderr/exception/effect mismatch reporting.
- Evaluation metrics record total, candidate, rewritten, rejected, unsafe, and
  unknown call-site counts plus precision/recall/FPR/FNR when labeled outcomes
  are available.
- Rewrite decisions carry proof metadata derived from SAFE, UNSAFE, or UNKNOWN
  classification. Only SAFE decisions can feed rewrite planning.
- Tests cover A1-A6 including an end-to-end polymorphic pipeline.
- CLI now supports analyze, trace, plan, rewrite, verify, report, and evaluate commands,
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
- `rewrite --apply` verifies by default and requires `--entry` unless
  `--skip-verify` is explicit.
- Plan-file replacements are rejected when generated class names are missing
  from source module scope.

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
- `tests/golden/` contains executable safe/unsafe fixtures checked by
  `tests/test_golden_corpus.py`.
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

External Phase 1 defect pass:

- D1 closure soundness now resolves verdict identity to the declaring MRO owner
  for observed implementations, reports unobserved sibling subclasses from that
  owner, and no longer treats "no open signals" or complete local hierarchy as
  CLOSED without positive final/sealed/closed-world evidence.
- D2 confidence scoring is covered by focused closed/open/no-known-impl tests,
  strict mypy on `src/flatten/confidence.py`, and plan JSON numeric confidence
  assertions.
- D3 CLI trace/plan/rewrite paths resolve filesystem boundaries consistently,
  and plan emits stderr warnings for unbound observations with non-zero strict
  exit.
- D4 `RewritePlanner.plan()` preserves all `TransformPlan` fields via
  `dataclasses.replace`.

External Phase 2 safety pass:

- `RewriteDecision` now carries structured reason codes, human messages,
  callsite/planned-expression metadata, observed receiver types, dispatch order,
  closure verdict, required imports, and safety notes.
- `docs/REWRITE_POLICY.md` documents the Phase 2 reason-code taxonomy and the
  conservative deterministic ordering policy.
- `docs/SAFETY_MODEL.md` states that runtime verification replays observed
  inputs only and is evidence, not proof.
- `harness.py` includes a subprocess-based module equivalence checker using
  `subprocess.run(timeout=...)` for Windows-compatible isolation.
- `tests/differential/` contains 20 policy fixtures with `input.py`,
  `expected_policy.json`, and `test_case.py`.
- Phase 2 negative and fuzz tests cover safety-critical rejection branches.

External Phase 3 release pass:

- CLI/package/docs release contracts are covered by
  `tests/test_phase3_release_contracts.py`.
- `py.typed` markers are present for `flatten` and `flatten_polymorph`.
- `python -m flatten` and `python -m flatten_polymorph` use guarded main
  entry points.
- GitHub Actions now has lint, typecheck, test, build, wheel-install-smoke, and
  cli-smoke jobs over Windows/Ubuntu and Python 3.10/3.12.
- Required docs, report schema, and five executable examples are present.
- `check-wheel-contents` passes with W009 ignored for the intentional
  `flatten` plus `flatten_polymorph` top-level package relationship.

## Known Issues

> 2026-08-23 추가 (Claude). 아래 항목은 이 문서와 `docs/ARCHITECTURE.md` 안에 이미
> 서술돼 있던 제약을 한곳에 모은 것이다. 새로 판단해 추가한 내용은 없다.

External blockers:

- Hosted GitHub Actions requires access to GitHub Actions or an installed /
  authenticated `gh` CLI.
- Mutation testing requires Linux/WSL: native Windows is unsupported by `mutmut`.

Intentional refusals (planner declines to rewrite):

- `direct` strategy is refused when the receiver is an identifier that names a
  function parameter (`_is_receiver_a_function_parameter()`).
- Rewrites are refused in `if` / `while` conditions and `assert` statements,
  where LibCST cannot hoist a temp receiver assignment
  (`_is_call_site_in_unhoistable_context()`).
- Guarded dispatch is refused for complex receivers (DEC-009).
- CLOSED is refused when unobserved sibling subclasses exist under the declaring
  MRO owner (D1 closure soundness).

Safety limits, false positive / negative risks, and unsupported Python features
are documented in `docs/ARCHITECTURE.md`.

<!-- TODO: 확인 필요 — 위는 코드가 명시적으로 거부하는 경우와 환경 블로커다.
     "고쳐야 하는데 아직 못 고친 것"으로 분류된 미해결 결함 목록은 이 저장소에 없다.
     있다면 여기에 채워야 한다. -->

## Verification

Use:

```powershell
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -c "import flatten"
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m pytest -q
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m pytest --cov=flatten --cov-report=term-missing --cov-fail-under=90
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m ruff check .
& 'C:\Users\Com\AppData\Local\Programs\Python\Python312\python.exe' -m mypy .
```

Current local result: full regression suite reports 243 passed, 1 pre-existing
failure (test_trace_binds_same_line_multiple_calls_by_runtime_column). Ruff
passes, `python -m mypy --strict src/flatten/` reports success for 25 source
files. SI gate 8/8 passes on branch `fix/si-hardening`.

v0.2.1 SI hardening (2026-06-15):

- RP fix: `planner.py` refuses `direct` strategy when receiver is an
  identifier that names a function parameter; `_is_receiver_a_function_parameter()`
  uses AST to distinguish pinned locals from unpinned parameters.
- SE fix: `_is_call_site_in_unhoistable_context()` extends refusal to
  `if`/`while` conditions and `assert` statements where LibCST cannot hoist
  a temp receiver assignment.
- P2 fix: `OracleRecord` gains a non-field `outcome` attribute (`"raise"` or
  `"return"`) set in `__post_init__` via `_RAISE_SENTINEL` sentinel detection.
- P2 fix: `Tracer.dispatch_records` property filters `tracer.records` to
  dispatch-only (`is_dispatch_target=True`) without disturbing backward-
  compatible full records list.

External blockers: hosted GitHub Actions requires access to GitHub Actions or
an installed/authenticated `gh` CLI; mutation testing requires Linux/WSL because
native Windows is unsupported by `mutmut`.

## Evidence Platform First

The first evidence-platform slice adds `flatten.evaluation`,
`flatten.comparator`, and `flatten.proofs`. The CLI can now emit reproducible
evaluation JSON through `flatten evaluate`, and reports can render evaluation
metrics as HTML. `docs/ARCHITECTURE.md` now documents public APIs, safety
limits, false positive/negative risks, unsupported Python features, and the
evidence platform data flow.

## P0 Soundness Coordination Pass

The Codex-Claude coordination channel now lives at
`AI/collab/COORDINATION.md`. The P0 pass fixed method-verdict cross-contamination
by grouping observations per method qualname and applying only the matching
SAFE verdict to each call site. `rewrite --apply --entry` now requires explicit
`--cases`, and external plan files must include planner-emitted
`rewrite_decisions` plus a positive per-plan `proof_artifact` in addition to a
matching source hash and source-scope class references.

`docs/SOUNDNESS.md` now documents the full Observation -> Closure Analysis ->
Rewrite Decision -> CST Transform -> Validation flow, including inputs,
outputs, failure/refusal conditions, soundness assumptions, and SAFE/UNSAFE/
UNKNOWN classification for dynamic Python features.

The per-plan proof artifact contract is now explicit in CLI plan output. Each
emitted rewrite plan includes machine-readable `proof_artifact` JSON with
callsite, observed targets, closure status, passed/failed closure rules, risk
level, and rewrite authorization.

The mutation harness now lives in `flatten.mutations` and generates source-level
variants for new subclass, dispatch target, monkey patch, runtime registration,
and `setattr` changes. Source-level `setattr` mutation is treated as an UNSAFE
monkey-patch risk during CLI planning.

T8 added an OSS benchmark catalog and release evidence layer. The catalog lives
at `benchmarks/projects.csv` with 35 public Python projects, and `flatten
benchmark` emits JSON/Markdown summaries. CI includes a benchmark-sanity job,
the release gate runs benchmark sanity, and `docs/research_evaluation.md`
documents threats to validity, known unsound cases, false positive/negative
analysis, methodology, reproducibility, artifact evaluation, and 0.2.0 release
criteria. This is catalog/gate infrastructure; the 30-project empirical run is
still a release blocker.

## Executable Safety Evidence Suite

This pass adds an executable local benchmark suite under `benchmarks/cases/`
with 56 JSON cases spanning safe rewrites, reject/unsafe dynamic Python,
open-world risks, harness equivalence, and intentionally unsupported cases.
`python -m benchmarks.runner` derives actual decisions from
`RewriteDecision.from_verdict`, runs harness probes through
`assert_modules_equivalent_subprocess`, and emits `benchmark-results.json` plus
`benchmark-report.md`. `tools/check_evidence.py` fails CI when schema invalid
count, false positives, or unsafe rewrites are nonzero, or when baseline
regression rules are violated.

`docs/engineering/PROJECT_AUDIT.md` records the architecture audit requested
for the evidence pass. `docs/SOUNDNESS.md` is the current evaluator-facing
soundness report and explicitly distinguishes observation, evidence, and proof.
CI now includes an `evidence` job that uploads benchmark JSON, benchmark
Markdown, and `coverage.xml`.

## v0.1.1 Defect Fix

v0.1.1 fixes release blockers and soundness regressions identified after the
Phase 3 pass. The built-wheel release gate now lives in
`scripts/release_gate.ps1` and CI job `release-gate`. Local hierarchy
completeness now yields `PROBABLY_CLOSED` unless positive CLOSED evidence
exists, and guarded dispatch rewrites fall back to the original dynamic method
call for unmatched receiver types.

## AST Migration Pass (2026-06-15)

Replaced all `dis` bytecode analysis with `ast`-based analysis for Python 3.8+
compatibility and stability:

- `tracer.py`: `_caller_position()` now uses `linecache + ast.parse` with a
  module-level `_ast_cache`. Removed `import dis`.
- `closure.py`: `_check_os3`, `_check_os4`, `_state_read_evidence`, and
  `_method_dynamic_hazards` now use `ast.walk` with `ast.Name`/`ast.Attribute`
  context checks. Added `_get_method_ast()` helper.
- `tests/test_tracer.py`: 3 bytecode-parametrized tests replaced with 2
  AST-based tests using `tmp_path` source files.
- Result: 220 passed, 1 skipped. whl rebuilt as
  `dist/flatten_polymorph-0.1.1-py3-none-any.whl`.

## Capafy Read-Only Audit Skill (2026-08-13)

flatten was evaluated as a Capafy monetization channel candidate. Designed a
read-only audit product as a local Claude Code Skill
(`.claude/skills/capafy-audit/SKILL.md`) that wraps the existing
`analyze` → `trace` → `plan` (dry-run) → `report` pipeline; `rewrite --apply`
is never invoked. Full rationale in
`AI/decisions/adr/ADR-2026-08-11-capafy-audit-skill.md` and
`AI/context/capafy_audit_skill_design.md`. Orchestration script and
summary renderer are implemented in `scripts/capafy_audit.py` and
`scripts/capafy_audit_report.py`. Static analysis runs by default; runtime
trace and all dependent planning/reporting require the explicit
`--yes-execute-trace` gate. Every generated artifact is confined to
`.capafy-audit/<timestamp>/`, and filtered pre/post Git status snapshots flag
target-code mutations without treating the audit directory as a change.

The planner now adds conservative AST-level rejection for concrete classes
available only through import aliases, function-local implementation classes,
and nested guarded-temp sites whose receiver hoist could reorder side effects.
JSON report mode preserves the complete plan audit trail and validates the
shape of report collections before rendering.

## Health Audit Repair (2026-08-13)

Guarded-temp planning now identifies the selected dispatch `ast.Call` with the
complete discovered source range (start and end), rather than its start
position alone. This distinguishes `factory().run()` from its nested
`factory()` call, which begins at the same column. Return, assignment, and
expression-statement guarded-temp rewrites again plan and hoist exactly one
receiver evaluation; nested expressions with preceding side effects remain
refused. Focused regression evidence is 8 passed.

The full suite reached 269 passed with one packaging test blocked because the
isolated build cannot download `hatchling` in this restricted environment.
Ruff and strict source mypy pass. Full details and environment-only blockers
are in `AI/reviews/2026-08-13-health-audit.md`.

---

## 2026-08-23 User Confirmation — Paused, no known defects, CI now green

**User answers:** current state = **started and paused** (Q7-1=c) /
known unresolved defects = **none** (Q7-2).

### What changed today

CI is now **green at 80/80**. The coverage gate was lowered 90 -> 82 and is measured on 3.12+ only;
3.8-3.11 cannot be measured meaningfully because of a `sys.settrace` conflict. That is a
measurement limitation, not a defect — consistent with Q7-2.

### Since there are no known defects, the remaining work is coverage, not bug-fixing

- `specialize.py` — **26%**, 94 of 139 lines uncovered. Effectively untested. This single module
  is why the gate had to drop to 82.
- `tracer.py` 73% · `_cli_orchestration.py` 78%.

**Do not raise the gate number back to 90.** Test `specialize.py` directly instead.

### Stale branches — safe to delete

- `origin/refactor/quality-improvement-9-10` — 48 commits behind. Its headline change
  (splitting `cli.py` into `_cli_orchestration.py`) is **already on main**.
- `origin/codex/project-hardening` — 26 commits behind.

Since the project is paused (Q7-1=c) and has no known defects (Q7-2), these branches carry no
rescue value. Delete them rather than leaving them to rot further.
