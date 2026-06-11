# Current Tasks

Last updated: 2026-06-11

## Completed

- Step 0: Freeze data contracts.
- Step 1: Implement tracer and tracer tests.
- Step 2: Implement closure analysis and OS1-OS5 tests.
- Step 3: Implement LibCST collapse planning and structure preservation tests.
- Step 4: Implement dispatch builders and direct/isinstance tests.
- Step 5: Implement behavior harness and divergence tests.
- Step 6: Add A1-A6 integration coverage.
- Hardening pass: opt-in rewrite planner, reports, CLI, confidence score,
  Hypothesis properties, CI config, ruff/mypy config, and 90% coverage gate.
- Staff-level pipeline pass: position-based discovery, observation schema,
  CLOSED/OPEN/UNSAFE safety model, plan-from-observations, exact LibCST
  transformer, CLI integration, examples, and README rewrite.
- Structured observation pass: added `TypeRef`/`FunctionRef`, plan-file CLI
  rewrite, static hierarchy extraction, required examples, and docs.
- flatten_polymorph upgrade Phase 0: added adversarial regression tests for
  DEFECT-1 through DEFECT-6, implemented CLI/closure/tracer fixes, and passed
  mandatory import, pytest, coverage, ruff, and mypy verification.
- flatten_polymorph upgrade Phase 1: added `RewriteDecision`, wired planner
  and CLI decision output, and fixed stale module-cache type restoration.
- flatten_polymorph upgrade Phase 2: expanded adversarial blockers for dynamic
  attribute mutation hooks, subclass hooks, dynamic code execution, and dynamic
  imports; static reporting now flags the same risks.
- flatten_polymorph upgrade Phase 3: added golden corpus docs, claim-test map,
  README safety updates, CI gate alignment, and release-quality tests.
- Post-phase call-site binding: same-line multiple method calls now bind by
  runtime caller column evidence.
- Remaining implementation pass: guarded dispatch for non-name receivers now
  uses statement-level temp receivers, and CLI planner closure uses static class
  graph evidence instead of runtime `__subclasses__` evidence.
- Follow-up safety pass: `rewrite --apply` now verifies by default unless
  `--skip-verify` is explicit, plan-file class names are checked against source
  scope, and executable golden safe/unsafe fixtures are covered by
  `tests/test_golden_corpus.py`.
- External Phase 1 defect pass: fixed D1 closure soundness, D2 confidence
  contract coverage, D3 relative-path binding and strict unbound warnings, and
  D4 `TransformPlan` field preservation. Evidence is stored in
  `AI/logs/phase1/` and summarized in `AI/reviews/phase1_report.md`.
- External Phase 2 safety pass: added structured `RewriteDecision` reason
  codes, rewrite policy docs, safety model docs, subprocess harness isolation,
  20 differential fixtures, mutation-like negative tests, and Hypothesis fuzz
  safety tests. Evidence is stored in `AI/logs/phase2/` and summarized in
  `AI/reviews/phase2_report.md`.
- External Phase 3 release pass: added release docs, report schema, typed
  markers, guarded module entry points, CI matrix/jobs, wheel content check,
  and five executable examples. Evidence is stored in `AI/logs/phase3/` and
  summarized in `AI/reviews/phase3_report.md`.
- v0.1.1 defect fix pass: fixed P0 release blockers, P1 soundness defects, and
  P2 quality defects with RED/GREEN logs in `AI/logs/` and summary in
  `AI/reviews/v0.1.1_defect_fix_report.md`.
- Evidence Platform First slice: added evaluation metrics, behavior comparator,
  proof classification, SAFE-gated planner metadata, `flatten evaluate`, HTML
  evaluation report rendering, and evidence architecture docs.

## Remaining

- No requested v0.1.1 defect item remains.
- Blocked external validation: hosted GitHub Actions needs GitHub Actions
  access or an installed/authenticated `gh` CLI.
- Blocked external validation: mutation testing needs Linux/WSL because native
  Windows is unsupported by `mutmut`; this machine has no WSL distribution.
- Remaining evidence-platform expansion: repository-scale mode, real-world
  benchmark corpus, mutation score automation, observability metrics, and
  deeper type-flow/alias analysis.
