# SQLite Memory

Primary database for MCP:

`	ext
AI/memory/sqlite/project_memory.sqlite
`

Schema contract:

`	ext
AI/memory/sqlite/schema.sql
`

Role split:

- Claude: read/query this memory during design and review.
- Codex: may update it only through explicit sync scripts or after implementation evidence exists.

If the SQLite file is absent, recreate it from schema.sql.