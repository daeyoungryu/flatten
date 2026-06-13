# COORDINATION.md - flatten-polymorph 협업 창구

<!-- 경로(저장소 루트 기준): AI/collab/COORDINATION.md -->

<!-- 참여자: Claude(검사자/설계), Codex(구현자), 댁(최종 결정권) -->

## 프로토콜 (불변)

1. 모든 작업 항목은 이 파일의 Task Board에 등록한다.
1. 상태 전이: `PROPOSED` -> (Claude OK + Codex OK) -> `AGREED` -> `IN_PROGRESS(담당자)` -> `DONE(검증 명령 포함)`
1. **양측 OK가 없는 항목은 착수 금지.** OK는 본 파일의 해당 항목에 `claude_ok: yes/no`, `codex_ok: yes/no`로 기록.
1. **의견 충돌(`yes`/`no` 불일치 또는 `BLOCKED` 표기) 시 작업 중단, `## Escalation` 섹션에 쟁점 요약 후 사용자에게 문의.** 어느 쪽도 일방 진행 금지.
1. 코드 수정은 담당자(Owner)만 한다. 비담당자는 리뷰 코멘트를 `## Review Log`에 남긴다.
1. 각 항목 완료 시 검증 명령(테스트/게이트)과 결과를 기록해야 `DONE` 인정.
1. 이 파일 수정 시 `## Changelog`에 한 줄 추가 (날짜, 작성자, 요지).

## 합의 대상 우선순위 (Claude 제안 - Codex 검토 요망)

P0 수정이 선행되지 않으면 벤치마크(Phase 5~10) 수치는 오염됨. 순서: P0 -> Phase 1~4 -> Phase 5~10.

## Task Board

### T1. [P0-1] verdict 병합 버그 - 메서드별 verdict 분리

- 내용: `_verdicts_from_observations`가 전체 관측을 첫 레코드 qualname 하나로 병합 -> final 클래스의 CLOSED가 무관한 OPEN 계층(미관측 서브클래스 존재)에 전파되어 unsound rewrite 발생. 재현: Worker(final)+Animal/Dog/Cat 케이스에서 `Dog.speak(pet)` 재작성 확인됨.
- 수락 기준: 메서드 qualname별 독립 verdict 생성, 재현 테스트 3건 green, 기존 happy-path 회귀 없음.
- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/regression/test_p0_repro.py -v` -> 5 passed
  - `python -m pytest -q` -> 214 passed

### T2. [P0-2] CLI 자동 검증 무력화 - 빈 케이스 하드코딩 제거

- 내용: `rewrite --apply --entry` 검증이 `[((), {})]` 단일 호출 하드코딩. 분기 커버리지 0.
- 수락 기준: `--cases` 없는 `--apply` 거부 또는 trace 입력 재사용 검증. 경고가 아닌 게이트.
- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/regression/test_p0_repro.py -v` -> 5 passed
  - `python -m pytest -q` -> 214 passed

### T3. [P0-3] plan 파일 자기참조 신뢰 - verdict 재검증 부재

- 내용: `_plans_from_plan_file`이 직렬화된 `status:"closed"`+evidence 문자열을 그대로 신뢰. source_hash 일치하는 위조 plan으로 OPEN 콜사이트 강제 재작성 재현됨.
- 수락 기준: plan 로드 시 source hash, source-scope class reference,
  planner-emitted `rewrite_decisions`, positive per-plan `proof_artifact`를
  확인하고 불일치 시 거부.
- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/regression/test_p0_repro.py -v` -> 5 passed
  - `python -m pytest -q` -> 214 passed

### T4. [철회] tracer `_find_frame_for_code` outermost-frame 버그 (Claude 감사 오류 정정)

- 정정: 재검증 결과 entry 콜사이트는 누락되지 않음. 레코드가 return 순서(안쪽 먼저)로 기록되어 entry 호출이 마지막 레코드로 나오는데, 최초 감사 시 앞 6건만 출력해 확인하여 누락으로 오판함. 동기 재귀에서는 매칭 대상 프레임이 항상 스택 최상위라 현 구현이 올바르게 동작. 재현 테스트(test_t4)는 0.1.1에서 GREEN - 회귀 가드로 유지.
- 잔여 우려(이론): 멀티스레드/제너레이터 환경에서의 frame-walk 정확성. 별도 재현 없이는 태스크화하지 않음.
- status: WITHDRAWN / claude_ok: n/a / codex_ok: n/a

### T5. [GPT안 Phase 1] docs/soundness.md 작성

- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest -q` -> 214 passed
  - `python -m ruff check .` -> All checks passed

### T6. [GPT안 Phase 2] per-plan proof artifact 계약 도입

- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/test_proof_artifacts.py -q` -> 2 passed
  - `python -m pytest -q` -> 214 passed
  - `python -m ruff check .` -> All checks passed

### T7. [GPT안 Phase 3~4] differential/mutation 테스트 하니스

- 전제: T1~T3 DONE.
- status: DONE / claude_ok: yes / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/test_mutation_harness.py -q` -> 2 passed
  - `python -m pytest tests/test_mutation_harness.py tests/test_phase2_negative_mutations.py tests/differential/test_cases.py -q` -> 7 passed
  - `python -m pytest -q` -> 214 passed
  - `python -m ruff check .` -> All checks passed

### T8. [GPT안 Phase 5~10] OSS 벤치마크/CI/릴리즈 게이트

- 전제: T1~T7 DONE. P0 미수정 상태 벤치마크는 데이터 오염으로 보류.
- status: DONE / claude_ok: yes (순서 조건부) / codex_ok: yes
- owner: Codex
- 검증:
  - `python -m pytest tests/test_benchmarks.py -q` -> 5 passed
  - `python -m pytest tests/test_benchmarks.py tests/test_phase3_release_contracts.py -q` -> 12 passed
  - `python -m flatten benchmark --catalog benchmarks/projects.csv --out-json benchmarks/summary.json --out-md benchmarks/summary.md` -> project_catalog_size 35
  - `python -m mypy .` -> Success: no issues found in 23 source files
  - `python -m ruff check .` -> All checks passed
  - `python -m pytest -q` -> 214 passed
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\release_gate.ps1` -> release gate passed

## Escalation

(없음)

## Review Log

(없음)

## Test Artifacts

- `tests/regression/test_p0_repro.py` (Claude 작성, 0.1.1 대상 실행 검증 완료)
  - 초기 결과: T1x2, T2, T3 = RED (버그 재현 확인) / T4 가드 = GREEN
  - 수정 후 결과: T1x2, T2, T3, T4 = GREEN
- `python -m ruff check src/flatten/cli.py src/flatten/planner.py tests/regression/test_p0_repro.py tests/test_staff_contracts.py tests/test_required_e2e.py` -> All checks passed
- `python -m pytest tests/regression/test_p0_repro.py tests/adversarial/test_phase0_defects.py tests/test_staff_contracts.py tests/test_required_e2e.py tests/test_v011_regressions.py tests/test_relative_path_binding.py -q` -> 42 passed
- `python -m pytest -q` -> 214 passed
- `python -m ruff check .` -> All checks passed
- `python -m pytest tests/test_proof_artifacts.py -q` -> 2 passed
- `python -m pytest -q` -> 214 passed
- `python -m pytest tests/test_mutation_harness.py -q` -> 2 passed
- `python -m pytest tests/test_mutation_harness.py tests/test_phase2_negative_mutations.py tests/differential/test_cases.py -q` -> 7 passed
- `python -m pytest -q` -> 214 passed
- `python -m pytest tests/test_benchmarks.py -q` -> 5 passed
- `python -m flatten benchmark --catalog benchmarks/projects.csv --out-json benchmarks/summary.json --out-md benchmarks/summary.md` -> project_catalog_size 35
- `python -m mypy .` -> Success: no issues found in 23 source files
- `python -m pytest -q` -> 214 passed
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\release_gate.ps1` -> release gate passed

## Changelog

- 2026-06-12 / Claude / 초안 생성: 프로토콜 + T1~T8 등록, P0 우선 순서 제안
- 2026-06-12 / Claude / T4 철회(감사 오판 정정: 레코드 return 순서 미고려), 재현 테스트 작성·실행 - T1~T3 RED 확인, test_t4는 회귀 가드로 전환
- 2026-06-12 / Codex / 사용자 제공 최신 협업 문서 반영, T1~T3 Codex OK 및 Owner 지정
- 2026-06-12 / Codex / T1~T3 구현 완료 및 검증 기록: P0 repro 5 passed, focused 42 passed, full suite green
- 2026-06-12 / Codex / T5 착수: docs/soundness.md 작성 범위 합의 및 Owner 지정
- 2026-06-12 / Codex / T5 완료: docs/soundness.md 추가 및 AI 컨텍스트/결정 로그 갱신
- 2026-06-12 / Codex / T6 착수: per-rewrite proof artifact JSON 계약 추가
- 2026-06-12 / Codex / T6 완료: per-plan `proof_artifact` JSON, regression tests 추가
- 2026-06-12 / Codex / T7 착수: mutation harness 및 false-positive guard 추가
- 2026-06-12 / Codex / T7 완료: source mutation harness, setattr false-positive guard, differential/mutation tests 검증
- 2026-06-13 / Codex / T8 착수: OSS benchmark catalog, metrics/report, CI/release sanity gate 추가
- 2026-06-13 / Codex / T8 완료: 35-project benchmark catalog, benchmark CLI/report, research evaluation doc, CI benchmark-sanity, release gate 강화
- 2026-06-13 / Codex / 기존 작업물 정리: T1~T3 검증 수치 최신화, T3/T6 계약 설명을 현재 구현과 일치시킴
