from pathlib import Path


def test_dis_migration_note_matches_source_fallbacks() -> None:
    source_uses_dis = any(
        "import dis" in path.read_text(encoding="utf-8")
        for path in Path("src/flatten").glob("*.py")
    )
    task_notes = Path("AI/tasks/current_tasks.md").read_text(encoding="utf-8")

    if source_uses_dis:
        assert "replaced all `dis` bytecode analysis" not in task_notes
        assert "source-unavailable bytecode fallback" in task_notes
