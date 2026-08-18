#!/usr/bin/env bash
# workflow-guard.sh — Claude Code PreToolUse hook (Bash/Git-Bash)
#
# 차단 대상:
#   1) git add . / git add -A
#   2) git push --force / git push -f
#   3) AI/tasks/current_tasks.md 없이 git commit
#   4) staged 삭제 10건 이상인 git commit   ← 대량 삭제 사고 방지
#
# 차단 시: exit 2 + stderr 메시지 → Claude Code가 tool 실행 거부

INPUT=$(cat)

# ---------------------------------------------------------------------------
# stdin(JSON)에서 command 추출
#
# 주의: Windows에는 Microsoft Store의 python3 "실행 별칭" 스텁이 존재한다.
#       command -v python3 은 성공하지만 실행하면 안내문만 출력하고 끝난다.
#       따라서 인터프리터는 실제 동작 여부를 검증한 뒤에만 사용한다.
#       (이 검증이 없어 예전 버전은 CMD가 항상 비었고 모든 규칙이 무력이었다.)
# ---------------------------------------------------------------------------
extract_cmd() {
  local py out
  for py in python3 python py; do
    command -v "$py" >/dev/null 2>&1 || continue
    # 실제 인터프리터인지 먼저 확인
    "$py" -c 'pass' >/dev/null 2>&1 || continue
    out=$(printf '%s' "$INPUT" | "$py" -c 'import json,sys
try:
    d = json.load(sys.stdin)
    t = d.get("tool_input") if isinstance(d, dict) else None
    if not isinstance(t, dict):
        t = d if isinstance(d, dict) else {}
    v = t.get("command", "")
    sys.stdout.write(v if isinstance(v, str) else "")
except Exception:
    pass' 2>/dev/null)
    if [ -n "$out" ]; then
      printf '%s' "$out"
      return 0
    fi
  done

  # 폴백: 콜론 앞뒤 공백을 허용하는 패턴 (구버전은 공백이 있으면 매치 실패했다)
  printf '%s' "$INPUT" | tr '\n' ' ' \
    | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    | head -1
}

CMD=$(extract_cmd)

# CMD를 못 읽었으면 파괴적 검사(규칙 4)는 그대로 수행한다 — fail-safe.
PARSED=1
[ -z "$CMD" ] && PARSED=0

# --------------------------------------------------- 규칙 1: git add . / -A
case "$CMD" in
  *"git add ."*|*"git add -A"*)
    >&2 echo "BLOCKED [workflow-guard]: 'git add .' / 'git add -A' 사용 금지."
    >&2 echo "  → 특정 파일을 명시하세요: git add <file1> <file2>"
    >&2 echo "  → 민감 파일(.env, 키) 실수 포함 방지를 위한 규칙입니다."
    exit 2
    ;;
esac

# --------------------------------------------------- 규칙 2: force push
case "$CMD" in
  *"git push"*"--force"*|*"git push"*"-f "*)
    >&2 echo "BLOCKED [workflow-guard]: Force push 금지."
    >&2 echo "  → 공유 브랜치 히스토리를 파괴합니다."
    >&2 echo "  → 꼭 필요하면 사용자가 터미널에서 직접 실행하세요."
    exit 2
    ;;
esac

# --------------------------------------------------- 규칙 3: 태스크 문서 존재
case "$CMD" in
  *"git commit"*)
    if [ ! -f "AI/tasks/current_tasks.md" ]; then
      >&2 echo "BLOCKED [workflow-guard]: AI/tasks/current_tasks.md 없이 커밋 불가."
      >&2 echo "  → 스펙/태스크 없는 커밋을 방지합니다."
      >&2 echo "  → ai-dev-scaffold 스킬로 AI/ 폴더를 먼저 생성하세요."
      exit 2
    fi
    ;;
esac

# --------------------------------------------------- 규칙 4: 대량 삭제 차단
DELETION_THRESHOLD=10
check_deletions=0
case "$CMD" in
  *"git commit"*) check_deletions=1 ;;
esac
# 명령을 파싱하지 못한 경우에도 검사한다 (안전 우선)
[ "$PARSED" -eq 0 ] && check_deletions=1

if [ "$check_deletions" -eq 1 ]; then
  DEL=$(git diff --cached --diff-filter=D --name-only 2>/dev/null | grep -c . || true)
  [ -z "$DEL" ] && DEL=0
  if [ "$DEL" -ge "$DELETION_THRESHOLD" ]; then
    >&2 echo "BLOCKED [workflow-guard]: staged 삭제 ${DEL}건 (임계값 ${DELETION_THRESHOLD})."
    >&2 echo "  → 과거 단일 커밋 291파일 삭제 사고의 재발을 막는 규칙입니다."
    >&2 echo "  → 삭제 목록: git diff --cached --diff-filter=D --name-only"
    >&2 echo "  → 의도한 대량 삭제라면 사용자가 터미널에서 직접 커밋하세요."
    exit 2
  fi
fi

exit 0
