# Obsidian Bridge

This folder records how project-local AI context maps to the external Obsidian vault.

- Local context: AI/context/
- External vault folder: C:\Users\Com\Documents\Obsidian Vault\Projects\flatten
- Bridge file: AI/obsidian/vault_link.md

## Current Memory Contract

- Structured memory: AI/memory/sqlite/project_memory.sqlite
- Semantic memory: data/memory.db via memory_store.py
- Memory seed document: AI/context/memory_seed.md when present

Keep secrets out of tracked files. Use .env.example for non-secret defaults only.