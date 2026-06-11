# Phase 1 Report

Date: 2026-06-11

## 1. Executive Summary

Phase 1 D1-D4를 완료했다.

- D1: 관측 구현체 qualname이 아니라 MRO상 선언 클래스 기준으로 closure verdict를 계산하도록 수정했다. `Circle.area`/`Square.area` 관측 시 기준은 `Shape.area`가 되며, 미관측 sibling `Triangle`은 blocker로 남고 rewrite plan은 생성되지 않는다.
- D2: `confidence_score()`의 float 반환 계약을 closed/open/no-known-impl 분기로 고정하는 테스트를 추가했다. 현재 구현은 이미 완성되어 있어 D2 단독 RED는 재현되지 않았다.
- D3: CLI/discovery/tracer 경계에서 경로를 resolve하여 상대 경로 trace -> plan -> rewrite가 binding되도록 수정했다. plan 0건 + unbound observation 존재 시 stderr warning을 출력하고 `--strict`에서는 비정상 종료한다.
- D4: `RewritePlanner.plan()`이 `TransformPlan`을 위치 인자로 재생성하지 않고 `dataclasses.replace()`로 보존하도록 수정했다.

남은 리스크: Phase 2 범위의 구조화된 reason code 전체 목록, 더 강한 planner safety decision 모델, differential suite, subprocess 격리 harness 확장은 아직 진행하지 않았다.

## 2. Safety Evidence

RED 로그:

- `AI/logs/phase1/red_initial_phase1_focused.log`
  - D3 relative path binding 실패: `unbound_observations == 1`
  - D3 unbound strict warning 부재: `stderr == ""`
  - D4 field preservation 실패: `target_call_site`, `strategy`, `confidence`, `risk_flags`, `temp_receiver`, `receiver_expr` 유실
- `AI/logs/phase1/red_d1_adjusted_phase1_focused.log`
  - D1 실패: verdict가 `Circle.area`, `is_closed=True`
  - D3/D4 실패 재확인

GREEN 로그:

- `AI/logs/phase1/green_phase1_focused.log`
  - `7 passed in 2.98s`
- `AI/logs/phase1/green_full_pytest.log`
  - `133 passed in 10.78s`

Safety blockers/status evidence:

- 미관측 sibling subclass는 `OS5: unobserved subclasses` blocker로 남는다.
- CLOSED promotion에서 `local_complete = not open_signals` 계열 경로를 제거했다.
- CLOSED는 `typing.final`, explicit sealed root allowlist, `--closed-world` positive evidence 중 하나가 있어야 한다.
- unbound observation은 더 이상 조용한 성공으로만 끝나지 않고 stderr에 warning을 남기며, `--strict`에서는 exit code 1이다.

## 3. Test Evidence

Focused Phase 1:

```text
python -m pytest tests\test_soundness_unobserved_sibling.py tests\test_confidence_contract.py tests\test_relative_path_binding.py tests\test_planner_field_preservation.py -q
.......                                                                  [100%]
7 passed in 2.98s
```

Full regression:

```text
python -m pytest -q
........................................................................ [ 54%]
.............................................................            [100%]
133 passed in 10.78s
```

D2 type gate:

```text
python -m mypy --strict src\flatten\confidence.py
Success: no issues found in 1 source file
```

## 4. Build Evidence

Build:

- Log: `AI/logs/phase1/build.log`
- Result: `Successfully built flatten_polymorph-0.1.0.tar.gz and flatten_polymorph-0.1.0-py3-none-any.whl`

Clean venv wheel smoke:

- Log: `AI/logs/phase1/wheel_smoke.log`
- Commands verified:
  - `pip install --force-reinstall dist\flatten_polymorph-0.1.0-py3-none-any.whl`
  - `python -c "import flatten; print(flatten.__version__)"`
  - `python -m flatten --help`
- Result excerpt:

```text
Successfully installed flatten-polymorph-0.1.0 libcst-1.8.6 pyyaml-6.0.3
0.1.0
usage: flatten [-h] {analyze,trace,plan,rewrite,verify,report} ...
```

## 5. OPEN Issues

- Phase 2 reason-code model is not complete. Current Phase 1 blockers are still verdict blockers/open signals, not the final `RewriteDecision.reason_code` taxonomy requested for Phase 2.
- Runtime/static closure proof remains conservative. Locally complete class graphs without positive final/sealed/closed-world evidence remain OPEN by design.
- Behavior verification still has the existing observed-input limitation; stronger subprocess isolation and differential case coverage are Phase 2 work.
- GitHub Actions and mutation testing remain externally blocked as previously documented.

## 6. Files Changed

Production:

- `src/flatten/closure.py`
- `src/flatten/planner.py`
- `src/flatten/discovery.py`
- `src/flatten/tracer.py`
- `src/flatten/observations.py`
- `src/flatten/cli.py`

Tests:

- `tests/test_soundness_unobserved_sibling.py`
- `tests/test_confidence_contract.py`
- `tests/test_relative_path_binding.py`
- `tests/test_planner_field_preservation.py`
- `tests/test_staff_contracts.py`

AI records:

- `AI/context/project_summary.md`
- `AI/context/architecture.md`
- `AI/decisions/decision_log.md`
- `AI/tasks/current_tasks.md`
- `AI/logs/phase1/*`
- `AI/reviews/phase1_report.md`
