#!/usr/bin/env bash
# workflow-guard 디스패처 — 로직은 정본 한 곳에만 있다.
#
# 정본: ~/.claude/templates/new_project_template/.claude/hooks/workflow-guard.sh
# 이 파일은 규칙을 복제하지 않는다. 예전에는 저장소마다 사본이 있어 정본을
# 고쳐도 배포된 사본에는 전파되지 않았다(force-push 구멍이 그렇게 남았다).
#
# 정본이 없으면 차단 쪽으로 실패한다 — 안전장치가 조용히 사라지면 안 되므로.

CANONICAL="${HOME}/.claude/templates/new_project_template/.claude/hooks/workflow-guard.sh"

if [ ! -f "$CANONICAL" ]; then
  >&2 echo "BLOCKED [workflow-guard]: 정본 훅을 찾을 수 없습니다: $CANONICAL"
  >&2 echo "  → 안전장치가 비활성 상태로 진행하지 않습니다."
  exit 2
fi

exec bash "$CANONICAL"
