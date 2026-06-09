# flatten — Codex 지침

## 한 줄 정의
런타임 추적(sys.monitoring) + CST 변환(LibCST)으로 다형 호출을 단일 실행 경로로 펼친다.

## 비목표 (절대 구현 금지)
- N1: 타입 추론 / 정적 분석으로 디스패치 결정 — 반드시 런타임 oracle 사용
- N2: 원본 코드 의미 변경 — 변환 전후 동등성 보장 필수
- N3: 미관측 분기 silently 제거 — 열린 계층은 stub으로 명시
- N4: sys.monitoring 없이 trace — monkey-patch / sys.settrace 사용 금지

## 빌드 순서 (이 순서 반드시 준수)
1. oracle (tracer.py) — 어떤 구현이 실행됐는지 확정
2. closure (closure.py) — 닫힌/열린 계층 판정
3. collapse (collapse.py) — 데이터 분기 변환
4. dispatch (dispatch.py) — 다형 호출 펼침
5. verify (harness.py) — 동등성 검증
6. inline — 최종 단일 로직 출력

## 데이터 계약 (변경 전 반드시 freeze)
- `OracleRecord`: `{qualname: str, impl_class: type, args: tuple, kwargs: dict, return_val: Any}`
- `ClosureVerdict`: `{method_qualname: str, is_closed: bool, known_impls: list[type], open_signals: list[str]}`
- `TransformPlan`: `{target_node: CSTNode, replacement: CSTNode, verdict: ClosureVerdict}`

## 하드 룰
1. 데이터 계약(OracleRecord, ClosureVerdict, TransformPlan) 인터페이스 먼저 freeze → 구현
2. 각 모듈은 단독 import 가능해야 함 (순환 의존 금지)
3. Python 3.12+ 전용 (`sys.monitoring` API)
4. 모든 변환은 LibCST 사용 (ast.unparse 금지)
5. 커밋 단위: feat → test → docs 순서 유지
