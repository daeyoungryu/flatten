#!/usr/bin/env bash
# workflow-guard 디스패처 — 로직은 정본 한 곳에만 있다.
#
# 이 파일은 규칙을 복제하지 않는다. 예전에는 저장소마다 사본이 있어 정본을
# 고쳐도 배포된 사본에는 전파되지 않았다(force-push 구멍이 그렇게 남았고,
# MyDAW 사본은 python3 탐지 실패로 세 규칙이 통째로 no-op 이었다).
#
# 정본 탐색 순서:
#   1) $WORKFLOW_GUARD_CANONICAL      — 명시 지정(테스트/이식용)
#   2) ~/.claude/templates/...        — 기본 정본
#   3) <Projects>/new_project_template/.claude/hooks/workflow-guard.sh
#                                     — git 으로 추적되는 백업
#
# 2번은 버전 관리되지 않는 단일 파일이라 유실 시 모든 저장소가 동시에 막힌다.
# 3번 폴백이 그 단일 실패점을 없앤다.
#
# 어느 것도 없으면 차단 쪽으로 실패한다 — 안전장치가 조용히 사라지면 안 되므로.

# 자기 위치에서 워크스페이스 루트를 역산한다.
#   <workspace>/<repo>/.claude/hooks/workflow-guard.sh
_self="${BASH_SOURCE[0]:-$0}"
_hooks_dir="$(cd "$(dirname "$_self")" 2>/dev/null && pwd)"
_repo_root="$(cd "${_hooks_dir}/../.." 2>/dev/null && pwd)"
_workspace_root="$(dirname "${_repo_root:-/}")"

C1="${WORKFLOW_GUARD_CANONICAL:-}"
C2="${HOME}/.claude/templates/new_project_template/.claude/hooks/workflow-guard.sh"
C3="${_workspace_root}/new_project_template/.claude/hooks/workflow-guard.sh"

for _c in "$C1" "$C2" "$C3"; do
  if [ -n "$_c" ] && [ -f "$_c" ]; then
    exec bash "$_c"
  fi
done

>&2 echo "BLOCKED [workflow-guard]: 정본 훅을 어디서도 찾지 못했습니다."
>&2 echo "  1) \$WORKFLOW_GUARD_CANONICAL : ${C1:-(미설정)}"
>&2 echo "  2) $C2"
>&2 echo "  3) $C3"
>&2 echo "  → 안전장치 없이 진행하지 않습니다."
>&2 echo "    정본을 복구하거나 WORKFLOW_GUARD_CANONICAL 로 경로를 지정하세요."
exit 2
