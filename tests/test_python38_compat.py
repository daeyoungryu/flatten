import ast
from pathlib import Path


def test_source_avoids_python310_zip_strict_runtime_dependency():
    offenders = []
    for path in Path("src/flatten").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "zip(" in text and "strict=" in text:
            offenders.append(str(path))

    assert offenders == []


def test_source_avoids_runtime_subscript_of_collections_abc_imports():
    offenders = []
    for path in Path("src/flatten").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        collections_abc_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "collections.abc":
                collections_abc_names.update(alias.asname or alias.name for alias in node.names)

        if not collections_abc_names:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Subscript):
                value = node.value.value
                if isinstance(value, ast.Name) and value.id in collections_abc_names:
                    offenders.append(f"{path}:{node.lineno}:{value.id}")

    assert offenders == []


def test_source_avoids_runtime_subscript_of_builtin_generics():
    offenders = []
    builtin_generic_names = {"dict", "frozenset", "list", "set", "tuple", "type"}
    for path in Path("src/flatten").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Subscript):
                continue
            value = node.value.value
            if isinstance(value, ast.Name) and value.id in builtin_generic_names:
                offenders.append(f"{path}:{node.lineno}:{value.id}")

    assert offenders == []
