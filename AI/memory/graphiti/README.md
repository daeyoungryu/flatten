# Graphiti Memory

Project Graphiti contract:

- Config: graphiti_config.py
- Sync script: graphiti_sync.py
- Entity seed: AI/context/graphiti_entities.md
- Export path: AI/memory/graphiti/export/
- Import path: AI/memory/graphiti/import/

Role split:

- Claude owns graph interpretation for architecture/design/review.
- Codex reads graph context when implementing but should not mutate graph memory unless the task explicitly asks for sync.

A runtime Graphiti MCP server command is not hard-coded here because this repo currently exposes sync scripts/config contracts, not a verified MCP server entrypoint.