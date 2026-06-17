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

---

## Git 워크플로우 규칙

- 어떤 작업이 완료되면 반드시 `git add -A && git commit && git push`를 수행한다
- `git status`는 항상 clean 상태를 유지한다
- commit 전에 오류/경고가 있다면 오류 내용을 commit 메시지 본문(body)에 포함시킨다:
  ```
  feat: 기능 구현

  [오류/경고 기록]
  - lint warning: xxx
  - test failure: yyy (known issue, tracked)
  ```
- 오류가 있더라도 push를 생략하지 않는다. 오류는 기록해서 남긴다

---

## Obsidian LLM 위키 운영 원칙

### 철학
위키는 LLM(나)이 읽기 위해 설계된 구조화 데이터다.
사람은 검토자(reviewer)이지 독자가 아니다.
모든 항목은 LLM이 코드 생성/판단 시 즉시 적용 가능한 형태로 작성한다.

> **참고:** flatten의 기존 `AI/patterns/patterns.md`와 `AI/decisions/decision_log.md`는
> LLM-first 위키와 동일한 역할을 이미 수행 중이다. 위키는 그 확장이다.

### 위키 경로
`C:\Users\Com\Documents\Obsidian Vault\Projects\flatten\wiki\`
(Obsidian 경로가 현재 미설정 — 사람이 `C:\Users\Com\Documents\Claude\Projects\CLAUDE.md`의 공유 경로 섹션 참조하여 생성)

### 위키 폴더 구조
```
wiki/
├── conventions/    # flatten 특화 코드 경계 규칙 (contracts.py, tracer.py 사용 규칙)
├── domain/         # Python sys.monitoring/sys.settrace 동작 제약 (버전별)
├── errors/         # 순환 임포트, pyc 캐시, LibCST 관련 반복 오류
└── decisions/      # AI/decisions/decision_log.md 미러 (검색 편의용)
```

### 위키에 넣을 것 (LLM이 모르는 것만)
- `contracts.py` 경계 규칙: 어떤 모듈이 임포트 가능하고 불가능한지
- `sys.monitoring` TOOL_ID 값과 버전별 동작 차이 (실험으로 확인된 것)
- LibCST를 `tracer.py`에서 쓰면 안 되는 이유 (실제 발생한 문제)
- pyc 캐시로 인한 반복 오류 패턴과 `touch` 명령 해결법
- 벤치마크 기준값 (bench/ 결과 기반 성능 임계값)

### 위키에 넣지 말 것 (LLM이 이미 앎)
- Python `sys.monitoring` API 공식 문서 내용
- LibCST 기본 사용법
- pytest 설정 방법

### 위키 항목 추가 트리거
1. **크리티컬 경계 위반 오류 발생 후** → `errors/` 에 증상 + 해결법 기록
2. **Python 버전별 동작 차이 발견 후** → `domain/` 에 기록
3. **새 모듈 경계 결정 후** → `conventions/` 에 기록
4. **`AI/decisions/decision_log.md` 항목 추가 후** → `decisions/` 미러에도 추가

### 항목 작성 형식
```
## [YYYY-MM-DD] 제목
**컨텍스트:** 어떤 상황에서 적용되는가
**규칙/패턴:** 구체적으로 무엇을 해야 하는가
**이유:** 왜 이 결정을 했는가 (필수)
**반례:** 적용하지 말아야 할 경우
```

### 초기 위키 항목 (사람이 Obsidian에서 생성할 것)
**`wiki/conventions/module_boundaries.md`**
- contracts.py 임포트 허용 모듈 목록
- LibCST 사용 허용/금지 파일 목록

**`wiki/domain/sys_monitoring_quirks.md`**
- Python 3.12+ sys.monitoring TOOL_ID=6 동작 확인된 엣지케이스
- 3.8~3.11 sys.settrace fallback 필요한 상황

**`wiki/errors/pyc_cache_issues.md`**
- pyc 캐시 오류 증상: 코드 수정 후에도 구버전 동작
- 해결: `touch src/flatten/모듈.py` 또는 `find . -name "*.pyc" -delete`
