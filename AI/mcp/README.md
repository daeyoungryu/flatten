# MCP Setup

Role split:

- Claude: design, architecture review, knowledge review.
- Codex: source implementation and local verification.

Active local MCP is project-scoped filesystem via root .mcp.json.

Contracts in this folder:

- filesystem.json
- sqlite.json
- obsidian.json

SQLite and Obsidian are recorded as contracts until their local MCP runtime entrypoints are verified. (sqlite-vec memory / `memory_store.py` do not exist in this repository — 2026-10-07 실측.)
