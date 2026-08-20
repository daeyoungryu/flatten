# flatten Health Audit — 2026-08-13

## Scope

Task 1 of `docs/superpowers/plans/2026-08-13-multi-project-health-and-hardening.md`:
reproduce and repair guarded-temp planning regressions, run local gates, and
exercise safe read-only workflows. No commit, push, installation, deployment,
or rewrite apply operation was performed.

## Root Cause and Repair

The five failing guarded-temp tests all planned `factory().run()`. Python AST
assigns that outer dispatch call and the nested `factory()` call the same start
position. `_guarded_temp_preserves_evaluation_order()` matched only that start
position, obtained two candidates, and conservatively returned `False`. This
suppressed plans for otherwise safe whole-statement contexts.

The minimal repair adds `end_lineno` and `end_col_offset` to the match. The
discovery contract already supplies those values, so the planner now selects
the exact outer dispatch call before checking whether it is a return,
assignment, annotated assignment, or expression-statement value. The test
helper was corrected to use the true call-site end column.

## TDD Evidence

RED (before production change):

```text
python -m pytest tests/regression/test_guarded_temp_statement_contexts.py -q -vv
3 failed: return, assignment, expression-statement plans were empty

python -m pytest tests/test_planner_ast_safety.py tests/test_si_regressions.py -q -vv
1 failed: whole return value was incorrectly refused

python -m pytest -q
5 failed, 265 passed, 1 warning
```

GREEN:

```text
python -m pytest tests/regression/test_guarded_temp_statement_contexts.py \
  tests/test_planner_ast_safety.py \
  tests/test_staff_contracts.py::test_guarded_dispatch_uses_temp_for_receiver_expression_with_side_effects -p no:cacheprovider -q
8 passed
```

## Verification

| Command | Result |
| --- | --- |
| `python -m ruff check src tests scripts` | Passed (`All checks passed!`) |
| `python -m mypy --strict src/flatten` | Passed (26 source files) |
| `python -m pytest -p no:cacheprovider --basetemp .health-pytest-utf8-20260813 -q` | 269 passed, 1 failed (external packaging blocker) |
| `python -m flatten --help` | Passed; all nine CLI commands listed |
| `python -m flatten analyze tests/golden/safe/final_with_attr_read.py --json` | Passed; one call-site candidate, no static risks |
| `python scripts/capafy_audit.py tests/golden/safe/final_with_attr_read.py` | Passed; static-only audit, no Git mutation warning |

Capafy output: `.capafy-audit/20260813T024622Z/analyze.json`. Trace was not
run because the Capafy audit contract requires a fresh explicit confirmation
before executing target code. No `rewrite` command was run.

## Blockers and Concerns

1. The full test suite's only failure is
   `tests/test_packaging.py::test_wheel_filename_pattern_after_build`. The
   isolated build attempts to download `hatchling`; outbound PyPI access is
   blocked (`WinError 10013`). A no-isolation build also cannot run because
   `hatchling.build` is not installed. No install was attempted.
2. `mypy .` reports the pre-existing Capafy script module twice as
   `capafy_audit_report` and `scripts.capafy_audit_report`. Strict source
   checking remains clean.
3. Repository example files checked during CLI smoke contain UTF-8 BOMs and
   `flatten analyze` currently rejects them. The smoke used a BOM-free golden
   fixture. This is a separate input-encoding compatibility issue, not part of
   the guarded-temp repair.
4. Two audit-created pytest directories, `.health-pytest-tmp-20260813/` and
   `.health-pytest-utf8-20260813/`, could not be removed even with elevated
   permission (`Access denied`). They contain only test temporary files and
   are untracked; no existing user file was altered.
