# ADR-2026-06-17: Project-local MCP role split

- Status: Accepted
- Date: 2026-06-17
- Tags: [mcp, context-engineering, handover, claude, codex]

## Context

This project is part of a multi-project AI-native workflow. Claude is used mainly for design and review. Codex is used mainly for source implementation. The project needs portable context assets so it can be handed over with code, knowledge, memory, and operational notes.

## Decision

Use project-local MCP configuration and memory contracts:

- `.mcp.json` declares active MCP servers for the project.
- `AI/mcp/` documents each server contract.
- `AI/memory/sqlite/project_memory.sqlite` stores structured project memory.
- `AI/obsidian/vault_link.md` records the Obsidian vault root and project folder.
- `AI/memory/graphiti/` records Graphiti import/export handover paths.

Role ownership:

- Claude owns design/review knowledge exploration across Obsidian, SQLite, and Graphiti.
- Codex owns source implementation through filesystem-scoped project access.

## Consequences

Positive:

- Each project can carry its own MCP and memory contract.
- Claude and Codex have clearer boundaries.
- Handover readiness improves because MCP, memory, and knowledge paths are explicit.

Trade-offs:

- Graphiti activation depends on project `.env` completeness.
- Obsidian MCP opens the vault root, so users should scope searches/edits to the project folder.
- SQLite MCP exposes write tools; memory mutation should be intentional.

## Current Status

Project: flatten

Active / ready servers:

```text
filesystem, sqlite, obsidian
```

Graphiti status:

```text
contract-ready-missing-env
```
