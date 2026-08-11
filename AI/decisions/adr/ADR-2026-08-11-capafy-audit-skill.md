# ADR-2026-08-11: Capafy read-only audit Skill

- Status: Accepted
- Date: 2026-08-11
- Tags: [capafy, monetization, skill, audit, read-only]

## Context

flatten은 Capafy의 수익화 채널 후보로 평가되었다. Capafy에 붙이려면 사용자
코드베이스에 대해 실행되는 read-only 감사(audit) 제품이 필요하다. flatten은
이미 정적 분석(`analyze`), 런타임 관측(`trace`), 계획 산출(`plan`, dry-run
기본), 리포트 생성(`report`/`evaluate`/`benchmark`)을 CLI로 제공하며, 실제
소스 변경은 `rewrite --apply`를 명시적으로 호출할 때만 발생한다. 이 경계를
그대로 활용하면 새 실행 엔진 없이 감사 제품을 구성할 수 있다.

## Decision

Capafy 감사 제품은 **로컬 Claude Code Skill(`SKILL.md`)**로 구현한다.
Capafy 서버사이드 배치 실행(사용자 코드 업로드 → Capafy 인프라에서 실행)은
채택하지 않는다.

세부 결정:

1. **실행 위치**: 사용자 자신의 로컬 Claude Code 세션. 사용자 자신의
   코드베이스를 사용자 자신의 환경에서 실행하므로 `pytest`를 로컬에서
   돌리는 것과 동일한 신뢰 경계이며, 별도의 코드 실행 샌드박스를 새로
   구축할 필요가 없다.
2. **감사 범위**: 정적 분석(`analyze`) + 런타임 관측(`trace`)을 모두
   포함한다. `plan`은 dry-run으로만 사용한다. `rewrite --apply`는 Skill이
   절대 호출하지 않는다.
3. **read-only 보장**은 "파일시스템 쓰기를 하지 않는다"로 범위를 좁힌다.
   코드 실행 자체의 샌드박싱은 사용자 책임 영역(자기 코드이므로)이라 Skill이
   새로 짊어지지 않는다. 대신 출력 격리, 명령 화이트리스트, 실행 전 확인
   게이트, git 상태 diff 검사로 안전망을 만든다.
4. **출력 포맷**: JSON(`report.json`, 기계판독) + 요약 마크다운
   (`summary.md`, 사람이 읽는 리포트)을 함께 생성한다.
5. **구현 위임**: SKILL.md에서 호출하는 오케스트레이션 스크립트, 출력
   디렉터리 관리, summary.md 렌더러는 Codex에 작업지시서로 위임한다. 이
   ADR 및 SKILL.md 초안 자체는 Claude가 작성한다.

상세 스펙은 `AI/context/capafy_audit_skill_design.md` 참고.

## Consequences

Positive:

- 새 실행 인프라(컨테이너/업로드 엔드포인트) 없이 기존 flatten CLI 경계만
  재사용해 감사 제품을 구성할 수 있다.
- read-only 보장 범위가 명확해져("파일시스템 쓰기 금지") 검증 가능한
  화이트리스트로 구현할 수 있다.
- Capafy 대시보드는 JSON을, 사용자는 summary.md를 각각 소비할 수 있어
  하나의 감사 실행으로 두 소비자를 만족시킨다.

Trade-offs:

- trace가 대상 코드를 실제로 실행하므로 부수효과 위험이 남는다 — 실행 전
  사용자 확인 게이트와 git status diff 검사로 완화하지만 100% 차단은
  아니다.
- 서버사이드 배치가 아니므로 Capafy가 사용자 개입 없이 코드베이스를
  스캔하는 완전 자동화 워크플로우는 이번 설계 범위 밖이다(후속 결정
  사항으로 남김).
- Skill은 사용자의 로컬 Python 환경에 flatten이 설치되어 있어야 동작한다.

## Current Status

Project: flatten

관련 문서:

- 디자인 스펙: `AI/context/capafy_audit_skill_design.md`
- SKILL.md 초안: `.claude/skills/capafy-audit/SKILL.md`
- Codex 작업지시서: `AI/tasks/codex_capafy_audit_orchestration.md`

구현 상태: 설계 완료, SKILL.md 초안 작성 완료, 실제 오케스트레이션
스크립트 구현은 Codex 위임 대기 중 (미착수).
