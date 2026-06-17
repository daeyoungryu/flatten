# Obsidian Bridge

This folder records how project-local AI context maps to the external Obsidian vault.

- Local context: AI/context/
- External vault: $vaultPath
- Bridge file: AI/obsidian/vault_link.md
"@

     = [ordered]@{
        mcpServers = [ordered]@{
            ("flatten-filesystem") = [ordered]@{
                command = 'npx'
                args = @('-y','@modelcontextprotocol/server-filesystem',C:\Users\Com\Documents\Claude\Projects\flatten)
            }
        }
    }
    Write-Json (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten '.mcp.json') 

    Write-Json (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\mcp 'filesystem.json') ([ordered]@{
        name = "flatten-filesystem"
        type = 'filesystem'
        status = 'active-safe'
        command = 'npx'
        args = @('-y','@modelcontextprotocol/server-filesystem',C:\Users\Com\Documents\Claude\Projects\flatten)
        root = C:\Users\Com\Documents\Claude\Projects\flatten
        owner = 'codex-primary'
        purpose = 'Codex source implementation and Claude project inspection scoped to this project root.'
    })

    Write-Json (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\mcp 'sqlite.json') ([ordered]@{
        name = "flatten-sqlite"
        type = 'sqlite'
        status = 'contract-ready'
        database = 'AI/memory/sqlite/project_memory.sqlite'
        absolute_database = (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\memory\sqlite 'project_memory.sqlite')
        schema = 'AI/memory/sqlite/schema.sql'
        owner = 'claude-design-review-primary'
        purpose = 'Structured project memory for design review, handover, decisions, and evaluation run history.'
        activation_note = 'Configure your installed SQLite MCP server to this database path. Do not hard-code secrets.'
    })

    Write-Json (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\mcp 'obsidian.json') ([ordered]@{
        name = "flatten-obsidian"
        type = 'obsidian'
        status = if (False) { 'contract-ready' } else { 'contract-ready-vault-path-not-found' }
        vault_path = C:\Users\Com\Documents\Obsidian Vault\Projects\flatten
        bridge = 'AI/obsidian/vault_link.md'
        owner = 'claude-primary'
        purpose = 'Architecture notes, design rationale, review notes, and operational knowledge.'
        env = [ordered]@{
            OBSIDIAN_VAULT_PATH = C:\Users\Com\Documents\Obsidian Vault\Projects\flatten
            OBSIDIAN_HOST = '127.0.0.1'
            OBSIDIAN_PORT = '27123'
            OBSIDIAN_API_KEY = ''
        }
    })

    Write-Json (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\mcp 'graphiti.json') ([ordered]@{
        name = "flatten-graphiti"
        type = 'graphiti'
        status = if (False -and False) { 'contract-ready-needs-runtime-entrypoint' } else { 'contract-created-config-missing' }
        config = 'graphiti_config.py'
        sync = 'graphiti_sync.py'
        entities = 'AI/context/graphiti_entities.md'
        export_dir = 'AI/memory/graphiti/export'
        import_dir = 'AI/memory/graphiti/import'
        owner = 'claude-design-review-primary'
        purpose = 'Project knowledge graph memory for architecture and context engineering.'
        env = [ordered]@{
            GRAPHITI_NEO4J_URI = ''
            GRAPHITI_NEO4J_USER = ''
            GRAPHITI_NEO4J_PASSWORD = ''
        }
        activation_note = 'Use graphiti_sync.py for current sync. Add an MCP server command only after a verified Graphiti MCP server entrypoint exists.'
    })

    Write-Utf8NoBom (Join-Path C:\Users\Com\Documents\Claude\Projects\flatten\AI\mcp 'README.md') @"
# MCP Setup

This project is configured for the current role split:

- Claude: design, architecture review, knowledge review.
- Codex: source implementation and local verification.

## Active Local MCP

The project root .mcp.json enables only the safe filesystem MCP scoped to this project root.

`	ext
flatten-filesystem -> C:\Users\Com\Documents\Claude\Projects\flatten
`

## Project MCP Contracts

- AI/mcp/filesystem.json: active-safe filesystem server contract.
- AI/mcp/sqlite.json: SQLite memory path and schema contract.
- AI/mcp/obsidian.json: Obsidian vault bridge contract.
- AI/mcp/graphiti.json: Graphiti config/sync/export contract.

SQLite, Obsidian, and Graphiti are recorded as contracts rather than blindly enabled runtime servers. This prevents Claude/Codex startup failures when a local MCP package or Graphiti MCP entrypoint is not installed yet.

## Recommended Use

Claude should load Obsidian, SQLite, and Graphiti context before design/review work.
Codex should use filesystem for code changes, then update AI/context, AI/decisions, or memory sync artifacts when the task requires it.