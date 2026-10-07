# Obsidian Bridge

This folder records how project-local AI context maps to the external Obsidian vault.

- Local context: AI/context/
- External vault folder: C:\Users\Com\Documents\Obsidian Vault\Projects\flatten
- Bridge file: AI/obsidian/vault_link.md

## Current Memory Contract

- Structured memory: AI/memory/sqlite/project_memory.sqlite
- Semantic memory: none — sqlite-vec scaffolding 저장소에 존재하지 않는다(2026-10-07 실측, 제거 커밋 없음); `memory_store.py` and `data/memory.db` are not in the repository.
- Memory seed document: AI/context/memory_seed.md when present

Keep secrets out of tracked files. Use .env.example for non-secret defaults only.