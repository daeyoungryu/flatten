#!/usr/bin/env bash
# workflow-guard.sh — Claude Code PreToolUse hook (Bash/Git-Bash)
# 차단 대상: git add . | git add -A | git push --force | git push -f
# 차단 시: exit 2 + stderr 메시지 → Claude Code가 tool 실행 거부

INPUT=$(cat)

# stdin에서 command 추출 (python3 없으면 grep fallback)
if command -v python3 &>/dev/null; then
  CMD=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    # tool_input.command or input.command
    print(d.get('tool_input', d).get('command', ''))
except Exception:
    print('')
" <<< "$INPUT" 2>/dev/null)
else
  CMD=$(echo "$INPUT" | grep -o '"command":"[^"]*"' | head -1 | sed 's/"command":"//;s/"//')
fi

# 규칙 1: git add . / git add -A 차단
case "$CMD" in
  *"git add ."*|*"git add -A"*)
    >&2 echo "BLOCKED [workflow-guard]: 'git add .' / 'git add -A' 사용 금지."
    >&2 echo "  → 특정 파일을 명시하세요: git add <file1> <file2>"
    >&2 echo "  → 민감 파일(.env, 키) 실수 포함 방지를 위한 규칙입니다."
    exit 2
    ;;
esac

# 규칙 2: git push --force / git push -f 차단
case "$CMD" in
  *"git push"*"--force"*|*"git push"*"-f "*)
    >&2 echo "BLOCKED [workflow-guard]: Force push 금지."
    >&2 echo "  → 공유 브랜치 히스토리를 파괴합니다."
    >&2 echo "  → 꼭 필요하면 사용자가 터미널에서 직접 실행하세요."
    exit 2
    ;;
esac

# 규칙 3: git commit 시 AI/tasks/current_tasks.md 존재 확인
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

exit 0
