# flatten — 프로젝트 현황
> 최종 갱신: 2026-06-09 | 담당: Claude Agent

## 개요
런타임 추적(sys.monitoring) + CST 변환(LibCST)으로 Python 다형 호출을 단일 실행 경로로 펼치는 패키지.

## 기술 스택
- 언어: Python 3.12+
- 프레임워크: 없음 (순수 라이브러리)
- 주요 의존성: libcst>=1.1.0, pytest>=8.0

## 완성도 현황

| 영역 | 완성도 | 비고 |
|------|--------|------|
| tracer.py | 30% | 기본 PY_START 추적 구현, impl_class 주입 미완 |
| closure.py | 40% | OS1~OS5 신호 구현, 일부 엣지케이스 미검증 |
| collapse.py | 30% | 단순 인라인 변환, 복잡 분기 미지원 |
| dispatch.py | 30% | isinstance 체인 생성 골격 완성 |
| harness.py | 60% | 동등성 검증 로직 완성 |
| 테스트 | 20% | tracer/closure 기본 테스트, A1~A6 미완 |
| 문서화 | 60% | AGENTS.md + .codex/skills 4개 완성 |

## 알려진 이슈 / 버그

| 날짜 | 파일 | 문제 | 상태 |
|------|------|------|------|
| 2026-06-09 | tracer.py | OracleRecord에 impl_class 실제 주입 미구현 | OPEN |
| 2026-06-09 | dispatch.py | build_isinstance_chain 모듈 경로 생성 단순화 필요 | OPEN |

## 외부 의존성 / 환경 설정

| 항목 | 값 | 비고 |
|------|----|------|
| Python | >=3.12 | sys.monitoring API 필수 |
| libcst | >=1.1.0 | CST 변환 |

## 변경 이력 (최근 3건)

| 날짜 | 변경 내용 |
|------|----------|
| 2026-06-09 | 프로젝트 초기 세팅 — 전체 구조 + AGENTS.md + Codex 스킬 4개 |
