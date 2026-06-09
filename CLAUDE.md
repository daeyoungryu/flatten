# flatten — Claude Code 운영 규칙

> **이식성 원칙:** 이 프로젝트를 다른 환경으로 포워딩하거나 독립 실행 시,
> 이 CLAUDE.md 전체와 `AI/global_rules.md`(공통 규칙)를 함께 포함한다.
> `AI/global_rules.md`는 모든 Cowork 프로젝트에 복사해서 사용한다.

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
├── logs/          # 프로젝트 타임라인 + lessons.db + lessons 노트
└── global_rules.md  # Cowork 공통 제약 규칙 (다른 프로젝트에 복사)
```

### 세션 시작 시 읽는 순서
1. `AI/global_rules.md` — Cowork 환경 제약 (파일 절단·pyc·git lock 등)
2. `AI/tasks/handoff_to_cc.md` — 이전 세션 브리핑
3. `AI/tasks/current_tasks.md` — 현재 우선순위
4. `AI/decisions/decision_log.md` — 결정 맥락
5. `AI/patterns/patterns.md` — 코딩 컨벤션

### 변경 후 갱신 순서
1. `AI/context/project_summary.md`
2. `AI/context/architecture.md`
3. `AI/decisions/decision_log.md`
4. `AI/tasks/current_tasks.md`

### Codex 작업 지시
`AI/tasks/task_template.md` 형식으로 지시서 작성 후 전달

---

## 프로젝트 특화 규칙 — flatten

### 크리티컬 경계
- 순환 임포트 금지: `contracts.py`만 공유 데이터 계층으로 임포트
- LibCST는 `tracer.py`에서 사용 금지 (collapse/dispatch 전용)
- `sys.settrace`는 Python 3.8~3.11 fallback 용도로만 허용

### 빌드 / 실행 방법
```bash
pip install -e . --break-system-packages
python -m pytest tests/ -x -q
```

### Python 버전 대응
- 3.12+: `sys.monitoring` 사용 (TOOL_ID = 6 for ExecutionTracer)
- 3.8~3.11: `sys.settrace` fallback

### 파일 작성 후 검증 체크리스트
```bash
# 1. AST 검증
python -c "import ast; ast.parse(open('src/flatten/모듈.py').read()); print('AST OK')"
# 2. pyc 무효화
touch src/flatten/모듈.py
# 3. 전체 테스트
python -m pytest tests/ -x -q 2>&1 | tail -3
```
