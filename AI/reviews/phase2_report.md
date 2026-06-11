# Phase 2 Report

Date: 2026-06-11

## 1. Executive Summary

Phase 2를 완료했다.

- Safety decision model: `RewriteDecision`에 structured `reason_code`,
  message, callsite id, original/planned expression, observed receiver types,
  dispatch order, closure verdict, required imports, safety notes를 추가했다.
- Rewrite policy: `docs/REWRITE_POLICY.md`에 reason code 표와 conservative
  ordering/refusal 정책을 문서화했다.
- Harness: `assert_modules_equivalent_subprocess()`를 추가해 원본/변환 모듈을
  subprocess로 격리 실행하고 stdout/stderr/return/exception/effects를 비교한다.
  timeout은 Windows 호환 `subprocess.run(timeout=...)`만 사용한다.
- Differential suite: `tests/differential/` 아래 20개 case directory를 추가했다.
  각 케이스는 `input.py`, `expected_policy.json`, `test_case.py` 구조를 가진다.
- Negative/fuzz: mutation-like negative tests와 Hypothesis fuzz safety tests를
  추가했다.

남은 리스크: Phase 2는 conservative refusal evidence를 강화했지만, Phase 3의
CLI schema/report packaging, full CI matrix, docs expansion, examples expansion은 아직
진행하지 않았다.

## 2. Safety Evidence

RED 로그:

- `AI/logs/phase2/red_phase2_core.log`
  - `RewriteDecision.reason_code` 없음
  - `RewritePlanner.decision_for_plan()` 없음
  - subprocess harness API 없음
  - `docs/REWRITE_POLICY.md`, `docs/SAFETY_MODEL.md` 없음
- `AI/logs/phase2/red_phase2_differential_negative_fuzz.log`
  - differential fixture collection/package 구조 문제 확인

GREEN 로그:

- `AI/logs/phase2/green_phase2_core_attempt.log`
  - `9 passed in 1.00s`
- `AI/logs/phase2/green_phase2_differential_negative_fuzz.log`
  - `26 passed in 0.95s`
- `AI/logs/phase2/green_phase2_full_pytest_attempt.log`
  - `168 passed in 12.87s`

Reason code 목록:

- `ALLOWED_CLOSED`
- `OPEN_CLOSURE_INCOMPLETE`
- `UNSAFE_NO_RECEIVER_TYPES`
- `UNSAFE_DYNAMIC_GETATTR`
- `UNSAFE_DYNAMIC_ATTRIBUTE_CALL`
- `UNSAFE_MONKEY_PATCH`
- `UNSAFE_MULTIPLE_INHERITANCE`
- `UNSAFE_UNRESOLVABLE_CLASS_REFERENCE`
- `UNSAFE_ALIAS_IMPORT`
- `UNSAFE_LOCAL_OR_NESTED_CLASS`
- `UNSAFE_DESCRIPTOR_OR_BINDING`
- `UNSAFE_CUSTOM_METACLASS`
- `UNSAFE_SUPER_DEPENDENCY`
- `UNSAFE_ARGUMENT_SIDE_EFFECTS`
- `UNSAFE_ASYNC_OR_GENERATOR`
- `UNSAFE_EXCEPTION_BEHAVIOR`
- `UNKNOWN_UNSUPPORTED`

## 3. Test Evidence

Core Phase 2:

```text
python -m pytest tests\test_phase2_rewrite_decisions.py tests\test_phase2_harness_subprocess.py -q
.........                                                                [100%]
9 passed in 1.00s
```

Differential / negative / fuzz:

```text
python -m pytest tests\differential tests\test_phase2_negative_mutations.py tests\test_fuzz_safety.py -q
..........................                                               [100%]
26 passed in 0.95s
```

Full regression:

```text
python -m pytest -q
........................................................................ [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
168 passed in 12.87s
```

Differential coverage:

- 20 case directories under `tests/differential/`
- Covered families: simple final success, sibling subclass, override-free
  subclass, diamond inheritance, multiple inheritance, `super()`, staticmethod,
  classmethod, property, descriptor, dynamic getattr, monkey patch, alias import
  placeholder, local class, nested class, async method, generator method,
  exception behavior, side-effect argument placeholder, closure incomplete.

## 4. Build Evidence

Build:

- Log: `AI/logs/phase2/build.log`
- Result: `Successfully built flatten_polymorph-0.1.0.tar.gz and flatten_polymorph-0.1.0-py3-none-any.whl`

Clean venv wheel smoke:

- Log: `AI/logs/phase2/wheel_smoke.log`
- Verified:
  - `pip install --force-reinstall dist\flatten_polymorph-0.1.0-py3-none-any.whl`
  - `python -c "import flatten; print(flatten.__version__)"`
  - `python -m flatten --help`

Result excerpt:

```text
Successfully installed flatten-polymorph-0.1.0 libcst-1.8.6 pyyaml-6.0.3
0.1.0
usage: flatten [-h] {analyze,trace,plan,rewrite,verify,report} ...
```

## 5. OPEN Issues

- Some Phase 2 differential fixtures are policy-level placeholders for planned
  Phase 3/next planner work, not full source-to-source rewrite E2E cases.
- The subprocess harness verifies observed inputs only. `docs/SAFETY_MODEL.md`
  explicitly documents this epistemic limit.
- Reason-code mapping is conservative and string-blocker based for existing
  closure blockers. A future AST-level planner pass can make class-reference,
  alias-import, side-effect, async/generator, and exception-behavior detection
  more precise.
- Linux-only mutation tooling remains not run on this Windows environment.

## 6. Files Changed

Production:

- `src/flatten/contracts.py`
- `src/flatten/planner.py`
- `src/flatten/harness.py`

Docs:

- `docs/REWRITE_POLICY.md`
- `docs/SAFETY_MODEL.md`

Tests:

- `tests/test_phase2_rewrite_decisions.py`
- `tests/test_phase2_harness_subprocess.py`
- `tests/test_phase2_negative_mutations.py`
- `tests/test_fuzz_safety.py`
- `tests/differential/**`

AI records:

- `AI/context/project_summary.md`
- `AI/context/architecture.md`
- `AI/decisions/decision_log.md`
- `AI/tasks/current_tasks.md`
- `AI/logs/phase2/*`
- `AI/reviews/phase2_report.md`
