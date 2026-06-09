# flatten — Claude Code 운영 규칙

> **이식성 원칙:** 이 프로젝트를 다른 환경으로 포워딩하거나 독립 실행 시,
> 이 CLAUDE.md 전체와 상위 전역 `~/.claude/CLAUDE.md`(공통 규칙)를 함께 포함한다.

## AI 조직 운영 원칙

이 프로젝트는 AI 기반 개발 조직 구조를 따른다.

### 역할 체계
사용자 → Claude(설계자/Wiki관리자) → Codex(구현자) → Claude(리뷰어) → Git

### AI 폴더 구조
```
AI/
├── agents/        # 각 AI 역할 정의
├── context/       # 프로젝트 컨텍스트 Living Document
├── decisions/     # 설계 의사결정 로그 (ADR)
├── patterns/      # 코딩 컨벤션 (진실원)
├── tasks/         # 작업 지시서 + handoff_to_cc.md
├── reviews/       # 리뷰 누적 기록
└── logs/          # 프로젝트 타임라인
```

### 세션 시작 시 읽는 순서
1. `AI/tasks/handoff_to_cc.md` — 이전 세션 브리핑
2. `AI/tasks/current_tasks.md` — 현재 우선순위
3. `AI/decisions/decision_log.md` — 결정 맥락
4. `AI/patterns/patterns.md` — 코딩 컨벤션

### 변경 후 갱신 순서
1. `AI/context/project_summary.md`
2. `AI/context/architecture.md`
3. `AI/decisions/decision_log.md`
4. `AI/tasks/current_tasks.md`

### Codex 작업 지시
`AI/tasks/task_template.md` 형식으로 지시서 작성 후 전달

## 프로젝트 특화 규칙

(이 섹션을 프로젝트에 맞게 채울 것)

### 크리티컬 경계
- (예: 오디오 스레드에서 메모리 할당 금지)

### 필수 환경변수
- (예: `.env.example` 참조)

### 빌드 / 실행 방법
```
(빌드 명령어)
```
