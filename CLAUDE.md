# flatten — Claude Code 운영 규칙

> **이식성 원칙:** 이 프로젝트를 다른 환경으로 포워딩하거나 독립 실행 시,
> 이 CLAUDE.md 전체와 `AI/global_rules.md`(공통 규칙)를 함께 포함한다.
> `AI/global_rules.md`는 모든 Cowork 프로젝트에 복사해서 사용한다.

## AI 조직 운영 원칙

역할 체계·AI 폴더 구조·세션 시작 시 읽는 순서·변경 후 갱신 순서·Codex 작업 지시 형식은
`Projects\CLAUDE.md` 가 정본이다. **여기서 중복 정의하지 않는다.**
게이트 운영 규약은 `Projects\docs\gate_protocol.md` 가 정본이다.

사용자 → Claude(설계) → Codex(설계 검증) → 합의 → Claude(구현) → Codex(구현 검증) → 합의 → Git

**설계와 구현은 Claude 가 직접 한다. Codex 는 두 게이트의 검증자로만 붙는다.**

> 2026-08-31 삭제. 이 자리에 `사용자 → Claude(설계자/Wiki관리자) → Codex(구현자) → Claude(리뷰어) → Git`
> 과 AI 폴더 구조·갱신 순서 사본이 남아 있었는데, `Projects\CLAUDE.md` 가 2026-08-23 에
> 그 배치를 폐기한 뒤였다. CLAUDE.md 는 git 저장소 경계를 넘어 로드되므로 두 파일이 매
> 세션 함께 실리고, 어느 쪽을 집을지가 세션마다 달라졌다. 규칙은 한 곳에만 둔다.

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

## Git 워크플로우

커밋·푸시는 `git-commit-safety-check` 스킬 절차를 따른다. `git add -A` 는 쓰지 않는다(훅이 차단한다). 푸시는 명시적 요청이 있을 때만 한다.

## Obsidian 위키

위키 항목 작성·수정은 `obsidian-wiki-entry` 스킬을 쓴다.
<!-- MCP_ROLE_SPLIT_2026_06_17 -->

## MCP 역할 규약

MCP 역할·경로 규약의 진실원은 `.mcp.json` 과 `AI/mcp/*.json` 이다. 필요할 때 읽는다.
