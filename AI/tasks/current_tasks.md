# Current Tasks
> 최종 갱신: 2026-06-09 | 담당: Claude(설계) + Codex(구현)

## 범례
- 우선순위: 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW
- 상태: ⏳ 대기 / 🔄 진행중 / ✅ 완료 / 🚫 차단됨
- 난이도: ★ 쉬움 / ★★ 보통 / ★★★ 어려움 / ★★★★ 매우 어려움

---

## TASK-001 ⏳ | 🔴 HIGH
**tracer.py — OracleRecord 완성 (impl_class 실제 주입)**

| 항목 | 내용 |
|------|------|
| 완성도 gap | 30% → 80% |
| 난이도 | ★★★ |
| 영향도 | 5 |
| 대상 파일 | src/flatten/tracer.py |
| 요약 | PY_RETURN 이벤트 추가로 반환값·self(impl_class) 캡처 |
| 완료 조건 | ① PY_RETURN 콜백 등록 ② OracleRecord.impl_class에 self.__class__ 주입 ③ test_tracer.py 통과 |
| 주의사항 | sys.monitoring TOOL_ID 전역 1개 유지 필수 |

---

## TASK-002 ⏳ | 🔴 HIGH
**수용 기준 A1~A6 통합 테스트 작성**

| 항목 | 내용 |
|------|------|
| 완성도 gap | 0% → 100% |
| 난이도 | ★★★ |
| 영향도 | 5 |
| 대상 파일 | tests/test_integration.py |
| 요약 | diamond.py 픽스처로 A1~A6 검증 |
| 완료 조건 | ① A1(5단계 다이아몬드) ② A2(닫힌 계층 isinstance) ③ A3(열린 계층 stub) ④ A4(OS1~OS5 각각) ⑤ A5(해시 동등성) ⑥ A6(포매팅 보존) |
| 주의사항 | AGENTS.md 빌드 순서(1→5) 준수 |

---

## TASK-003 ⏳ | 🟡 MEDIUM
**dispatch.py — build_isinstance_chain 모듈 경로 개선**

| 항목 | 내용 |
|------|------|
| 완성도 gap | 30% → 70% |
| 난이도 | ★★ |
| 영향도 | 3 |
| 대상 파일 | src/flatten/dispatch.py |
| 요약 | 클래스 모듈 경로를 정확히 qualified import로 생성 |
| 완료 조건 | ① 다중 모듈 클래스 처리 ② LibCST Attribute 체인 생성 ③ 단위 테스트 통과 |
| 주의사항 | ast.unparse 금지 — LibCST만 사용 |

---

## 완료된 태스크

| ID | 내용 | 완료일 |
|----|------|--------|
| SETUP | 프로젝트 초기 세팅 (구조 + AGENTS.md + 스킬 4개) | 2026-06-09 |
