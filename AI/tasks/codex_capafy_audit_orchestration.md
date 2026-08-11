# Codex 작업 지시: Capafy 감사 Skill 오케스트레이션 구현

**발급자:** Claude (설계자)
**대상:** Codex (구현자)
**우선순위:** MEDIUM
**브랜치:** `feature/capafy-audit-skill` (이미 생성됨, 이 브랜치에서 작업)
**선행 문서 (반드시 먼저 읽을 것):**
- `AI/decisions/adr/ADR-2026-08-11-capafy-audit-skill.md`
- `AI/context/capafy_audit_skill_design.md`
- `.claude/skills/capafy-audit/SKILL.md`

---

## 목표

`.claude/skills/capafy-audit/SKILL.md`가 호출하는 오케스트레이션 스크립트,
출력 디렉터리 관리, `summary.md` 렌더러를 구현한다. Claude가 이미 설계와
SKILL.md 초안을 작성했으므로 이 태스크는 **구현만** 담당한다. 설계를
바꾸고 싶으면 먼저 Claude에게 확인받을 것 — 특히 아래 "절대 규칙"은
협의 없이 변경 불가.

## 절대 규칙 (SKILL.md와 동일 — 구현에서도 강제할 것)

1. `flatten rewrite`는 어떤 형태로도 호출하지 않는다 (`--apply` 유무 무관).
2. `git status` 외의 `git` 서브커맨드를 실행하지 않는다.
3. 모든 출력은 `<repo>/.capafy-audit/<timestamp>/` 하위에만 쓴다. 소스
   트리 내부에는 아무것도 쓰지 않는다.
4. trace 단계(runtime 실행)는 스크립트가 자동으로 실행하지 않는다 —
   사용자 확인은 Skill 레벨(Claude Code 세션)에서 이루어지므로, 스크립트는
   trace 실행을 별도 단계/함수로 분리해서 confirm 없이 자동 연쇄 실행되지
   않도록 만든다 (예: `--yes-execute-trace` 같은 명시적 플래그 없이는
   trace 단계가 실행되지 않아야 함).
5. `--out`, `--observations`, `--plan` 등 모든 경로 인자는
   `.capafy-audit/<timestamp>/` 하위로만 강제한다 — 사용자가 다른 경로를
   넘겨도 거부하거나 하위 디렉터리로 재작성한다.

## 구현 범위

### 1. 오케스트레이션 스크립트 — `scripts/capafy_audit.py`

CLI 스크립트로 구현 (예: `python scripts/capafy_audit.py <scope> --entry <entry>`).

책임:
- Preflight: `git rev-parse --is-inside-work-tree` 확인, `git status
  --porcelain` PRE 스냅샷 캡처, `.capafy-audit/<timestamp>/` 생성,
  `python -c "import flatten"` 확인.
- Static pass: `flatten analyze` 호출 (subprocess), 결과를
  `.capafy-audit/<timestamp>/analyze.json`에 저장.
- Runtime pass: **별도 함수/서브커맨드로 분리**, 명시적 플래그
  (`--yes-execute-trace`) 없이는 실행하지 않음. 실행 시
  `flatten trace ... --out .capafy-audit/<timestamp>/observations.json`.
- Planning pass: `flatten plan ... --observations ... --out
  .capafy-audit/<timestamp>/plan.json` (dry-run만, `--apply` 플래그 자체를
  코드에 존재시키지 말 것).
- Reporting: `flatten report .capafy-audit/<timestamp>/plan.json`을
  `.capafy-audit/<timestamp>/report.json`으로 저장 후 `render_summary()` 호출.
- Postflight: `git status --porcelain` POST 스냅샷, PRE와 diff 있으면
  stdout에 경고를 최상단에 출력하고 non-zero 계열 신호(exit code는 0
  유지하되 경고 플래그를 stdout JSON에 포함 — 감사 자체는 성공이므로 실패로
  취급하지 않음, 단 눈에 띄게 표시).
- 명령 실패 시: 해당 단계에서 즉시 중단, stderr 그대로 출력, 이후 단계
  진행하지 않음. 자동 재시도 없음.

### 2. `summary.md` 렌더러 — `scripts/capafy_audit_report.py` (또는 위 스크립트에 통합)

`report.json`(flatten의 기존 리포트 스키마)을 입력으로 받아
`.capafy-audit/<timestamp>/summary.md`를 생성:
- 헤드라인: 총 call site 수, CLOSED 후보 수, UNSAFE 수
- UNSAFE 상위 N개 (file:line, hazard 카테고리)
- rewrite 후보 상위 N개 (file:line, confidence) — "참고용, 적용 안 됨" 명시
- 1문단 평문 총평
- git diff 경고가 있었다면 파일 최상단에 표시

정확한 `report.json` 스키마는 `src/flatten/`의 기존 report/evaluate
dataclass 정의를 참고할 것 (임의로 새 스키마를 만들지 말 것 — 이미 있는
`flatten report` 출력 구조를 그대로 소비).

### 3. 테스트

- `.capafy-audit/` 출력이 실제로 저장소 밖(전용 디렉터리)에만 생성되는지
  검증하는 테스트.
- `--apply` 관련 플래그/경로가 스크립트 코드 어디에도 존재하지 않는지
  검증하는 정적 검사 테스트 (예: 소스 문자열에 `--apply` 리터럴이 없는지
  grep 기반 회귀 테스트).
- trace 단계가 `--yes-execute-trace` 없이는 호출되지 않는지 검증하는
  테스트.
- git status 사전/사후 diff 감지 테스트 (mock 또는 임시 저장소로).

## 완료 조건

1. `python scripts/capafy_audit.py <scope>` 실행 시 static pass까지만
   자동 실행되고, trace는 별도 플래그 없이 실행되지 않는다.
2. `.capafy-audit/<timestamp>/` 외부에는 어떤 파일도 생성/수정되지 않는다
   (테스트로 확인).
3. 소스 코드 어디에도 `flatten rewrite --apply` 또는 `--apply` 호출 경로가
   없다 (grep 회귀 테스트로 확인).
4. `summary.md`가 기존 `flatten report` JSON 스키마를 그대로 소비해 생성된다.
5. `python -m pytest tests/ -x -q` 전체 통과.
6. `AI/context/capafy_audit_skill_design.md`와 `.claude/skills/capafy-audit/SKILL.md`에
   기술된 동작과 실제 스크립트 동작이 일치한다 (불일치 발견 시 스크립트를
   설계에 맞추거나, 설계 변경이 필요하면 구현 전에 Claude에게 알릴 것).

## 주의사항

- Cowork 환경 제약(`AI/global_rules.md`)을 따를 것 — 파일 절단, pyc 캐시,
  git lock 이슈 시 해당 문서의 해결법 사용.
- 이 브랜치(`feature/capafy-audit-skill`)에서만 작업. main에 직접 커밋 금지.
- 작업 완료 후 `AI/context/project_summary.md`와
  `AI/tasks/current_tasks.md`를 갱신할 것 (프로젝트 규칙).
