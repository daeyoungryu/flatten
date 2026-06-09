# Handoff to Claude Code — flatten
> 작성: Claude Agent | 날짜: 2026-06-09 | 세션: 초기 세팅

이 문서는 새 CC(Claude Code) 세션 시작 시 컨텍스트를 빠르게 전달하기 위한 브리핑입니다.
세션 시작 직후 이 파일을 읽어 현재 상태를 파악하세요.

---

## 현재 상태 요약

- **프로젝트 완성도:** ~30%
- **마지막 완료 작업:** [SETUP] 초기 세팅 (2026-06-09)
- **현재 브랜치:** `main`
- **빌드 상태:** ✅ 구조 완성, libcst 미설치 (실행 전 `pip install -e ".[dev]"` 필요)

---

## 미완성 작업 (우선순위 순)

1. **[TASK-001]** tracer.py — OracleRecord impl_class 실제 주입 — 상태: ⏳
   - 남은 완료 조건: ① PY_RETURN 콜백 ② self.__class__ 캡처 ③ 테스트 통과
2. **[TASK-002]** 수용 기준 A1~A6 통합 테스트 작성 — 상태: ⏳
3. **[TASK-003]** dispatch.py — isinstance 체인 모듈 경로 개선 — 상태: ⏳

> 전체 목록: `AI/tasks/current_tasks.md` 참조

---

## 알려진 제약 / 주의사항

- [환경] Python 3.12+ 전용 — `sys.monitoring` API
- [빌드] `pip install -e ".[dev]"` 먼저 실행 (libcst 설치)
- [코딩] `ast.unparse` 사용 금지 — LibCST만 사용
- [순서] AGENTS.md 빌드 순서 (oracle → closure → collapse → dispatch → verify) 준수

---

## 다음 단계 제안

1. **즉시 착수 권장:** TASK-001 — 전체 파이프라인의 첫 단계, 선행 조건 없음
2. **이후:** TASK-002 — TASK-001 완료 후 통합 테스트
3. **보류:** TASK-003 — TASK-001/002 이후 가능

---

## 이전 세션에서 결정된 사항

| 날짜 | 결정 | 근거 |
|------|------|------|
| 2026-06-09 | sys.monitoring 전용, sys.settrace 금지 | 성능 + Python 3.12 표준 API |
| 2026-06-09 | LibCST 전용, ast.unparse 금지 | 포매팅 보존 필수 |

> 전체 ADR: `AI/decisions/decision_log.md` 참조
