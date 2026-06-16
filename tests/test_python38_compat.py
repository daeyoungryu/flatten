from pathlib import Path


def test_source_avoids_python310_zip_strict_runtime_dependency():
    offenders = []
    for path in Path("src/flatten").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "zip(" in text and "strict=" in text:
            offenders.append(str(path))

    assert offenders == []
