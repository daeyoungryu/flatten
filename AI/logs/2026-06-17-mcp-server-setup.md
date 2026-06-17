# MCP Server Setup Record - flatten

Date: 2026-06-17
Owner: Codex
Purpose: Project-local MCP readiness for Claude design/review and Codex implementation work.

## Summary

Configured project-local MCP assets for this project.

Active / ready servers:

`	ext
filesystem, sqlite, obsidian
`

Graphiti status:

`	ext
contract-ready-missing-env
`

## Files Added Or Updated

- .mcp.json
- AI/mcp/README.md
- AI/mcp/filesystem.json
- AI/mcp/sqlite.json
- AI/mcp/obsidian.json
- AI/mcp/graphiti.json
- AI/memory/sqlite/schema.sql
- AI/memory/sqlite/project_memory.sqlite
- AI/memory/sqlite/README.md
- AI/memory/graphiti/README.md
- AI/memory/graphiti/export/.gitkeep
- AI/memory/graphiti/import/.gitkeep
- AI/obsidian/README.md
- AI/obsidian/vault_link.md

## Role Split

- Claude: design, architecture review, Obsidian/SQLite/Graphiti knowledge review.
- Codex: filesystem-scoped source implementation, test execution, local verification.

## MCP Runtime Decisions

- Filesystem MCP is active and scoped to this project root.
- SQLite MCP is active against AI/memory/sqlite/project_memory.sqlite.
- Obsidian MCP uses Seekstone against the vault root:

`	ext
C:\Users\Com\Documents\Obsidian Vault
`

Project note folder inside the vault:

`	ext
Projects/flatten
`

- Graphiti MCP remains contract-only because required Graphiti/Neo4j/OpenAI environment variables are not present for this project.

## Verification

- .mcp.json parsed successfully during setup verification.
- SQLite database was initialized with these tables:
  - project_context
  - decisions
  - operational_notes
  - evaluation_runs
- Obsidian vault root was validated by Seekstone: 162 markdown notes found.

## Follow-up

- If Graphiti is contract-only, add GRAPHITI_NEO4J_URI, GRAPHITI_NEO4J_USER, GRAPHITI_NEO4J_PASSWORD, and OPENAI_API_KEY or EMBEDDING_API_KEY to .env, then activate the Graphiti MCP runner.
- Claude/Codex sessions should reload MCP configuration after opening the project root.