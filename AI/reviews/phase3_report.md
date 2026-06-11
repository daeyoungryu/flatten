# Phase 3 Report

Date: 2026-06-11

## 1. Executive Summary

Phase 3을 완료했다.

- CLI/release contract tests added: `tests/test_phase3_release_contracts.py`.
- Packaging improved with metadata classifiers, `py.typed` markers, guarded
  `__main__` entry points, and `check-wheel-contents` validation.
- CI rebuilt into required jobs: lint, typecheck, test, build,
  wheel-install-smoke, cli-smoke over Windows/Ubuntu and Python 3.10/3.12.
- Docs added: architecture, unsupported cases, testing strategy, CLI, examples,
  roadmap, and rewrite report JSON schema.
- README updated to remove the unsafe local-complete CLOSED claim and state
  "Observation is evidence, not proof" plus safe reject policy.
- Five executable examples added and run.

남은 리스크: Hosted GitHub Actions 자체는 이 로컬 환경에서 실행하지 못했다.
CI workflow는 파일/테스트로 검증했고, 로컬 equivalent gates는 모두 exit 0이다.

## 2. Safety Evidence

RED logs:

- `AI/logs/phase3/red_quality_gate.log`
  - ruff failed on line length/import ordering/unused imports.
  - mypy failed on `harness.py` returning `Any`.
- `AI/logs/phase3/red_release_contracts.log`
  - required docs missing.
  - rewrite report schema missing.
  - classifiers and typed markers missing.
  - `__main__` modules lacked guards.
  - CI job matrix did not match Phase 3.
  - example directories missing.

GREEN logs:

- `AI/logs/phase3/green_release_contracts.log`
  - `6 passed in 0.30s`
- `AI/logs/phase3/green_quality_gate_final.log`
  - compileall exit 0
  - import exit 0
  - CLI help exit 0
  - pytest exit 0
  - ruff exit 0
  - mypy exit 0
  - build exit 0
- `AI/logs/phase3/wheel_smoke_and_check_final.log`
  - clean venv wheel install, import, CLI help, and check-wheel-contents pass.
- `AI/logs/phase3/examples.log`
  - all five examples exit 0.

Reason-code and safety docs remain in:

- `docs/REWRITE_POLICY.md`
- `docs/SAFETY_MODEL.md`
- `docs/UNSUPPORTED_CASES.md`

## 3. Test Evidence

Phase 3 release-contract tests:

```text
python -m pytest tests\test_phase3_release_contracts.py -q
......                                                                   [100%]
6 passed in 0.30s
```

Full quality gate:

```text
python -m compileall src\flatten
python -c "import flatten"
python -m flatten --help
python -m pytest -q
python -m ruff check .
python -m mypy src\flatten
python -m build
```

Final result excerpt:

```text
174 passed in 12.66s
All checks passed!
Success: no issues found in 16 source files
Successfully built flatten_polymorph-0.1.0.tar.gz and flatten_polymorph-0.1.0-py3-none-any.whl
```

Examples:

```text
examples\simple_dispatch_success\run.py -> ALLOWED_CLOSED
examples\multi_subclass_success\run.py -> ALLOWED_CLOSED
examples\dynamic_getattr_rejected\run.py -> UNSAFE_DYNAMIC_GETATTR
examples\monkey_patch_rejected\run.py -> UNSAFE_MONKEY_PATCH
examples\multiple_inheritance_rejected\run.py -> UNSAFE_MULTIPLE_INHERITANCE
```

## 4. Build Evidence

Build:

- Log: `AI/logs/phase3/build_final.log`
- Result: `Successfully built flatten_polymorph-0.1.0.tar.gz and flatten_polymorph-0.1.0-py3-none-any.whl`

Clean venv wheel smoke and wheel content:

- Log: `AI/logs/phase3/wheel_smoke_and_check_final.log`
- Verified:
  - `pip install --force-reinstall dist\flatten_polymorph-0.1.0-py3-none-any.whl`
  - `python -c "import flatten; print(flatten.__version__)"`
  - `python -m flatten --help`
  - `python -m check_wheel_contents dist\flatten_polymorph-0.1.0-py3-none-any.whl`

Result excerpt:

```text
Successfully installed flatten-polymorph-0.1.0 libcst-1.8.6 pyyaml-6.0.3
0.1.0
usage: flatten [-h] {analyze,trace,plan,rewrite,verify,report} ...
dist\flatten_polymorph-0.1.0-py3-none-any.whl: OK
```

## 5. OPEN Issues

- Hosted GitHub Actions was not executed locally. The workflow file and local
  equivalent commands pass.
- `check-wheel-contents` W009 is intentionally ignored because the package
  ships both the implementation package `flatten` and compatibility shim
  `flatten_polymorph`. README documents this relationship.
- Report schema is present and tested for required audit fields; deeper runtime
  schema validation can be expanded in a future release.

## 6. Files Changed

Production/package:

- `src/flatten/__main__.py`
- `src/flatten_polymorph/__main__.py`
- `src/flatten/py.typed`
- `src/flatten_polymorph/py.typed`
- `pyproject.toml`
- `.github/workflows/ci.yml`

Docs:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CLI.md`
- `docs/EXAMPLES.md`
- `docs/ROADMAP.md`
- `docs/TESTING_STRATEGY.md`
- `docs/UNSUPPORTED_CASES.md`
- `docs/rewrite_report.schema.json`

Examples:

- `examples/simple_dispatch_success/run.py`
- `examples/multi_subclass_success/run.py`
- `examples/dynamic_getattr_rejected/run.py`
- `examples/monkey_patch_rejected/run.py`
- `examples/multiple_inheritance_rejected/run.py`

Tests:

- `tests/test_phase3_release_contracts.py`

AI records:

- `AI/context/project_summary.md`
- `AI/context/architecture.md`
- `AI/decisions/decision_log.md`
- `AI/tasks/current_tasks.md`
- `AI/logs/phase3/*`
- `AI/reviews/phase3_report.md`
