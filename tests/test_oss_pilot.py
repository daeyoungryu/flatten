from pathlib import Path

from benchmarks.oss_pilot import evaluate_python_tree


def test_evaluate_python_tree_counts_call_sites_and_parse_failures(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "ok.py").write_text(
        "class Worker:\n"
        "    def run(self):\n"
        "        return 1\n"
        "def entry():\n"
        "    worker = Worker()\n"
        "    return worker.run()\n",
        encoding="utf-8",
    )
    (package / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    result = evaluate_python_tree(package)

    assert result["python_files"] == 2
    assert result["parsed_files"] == 1
    assert result["parse_failures"] == 1
    assert result["total_call_sites"] == 1
    assert result["candidates"] == 1
    assert result["rewritten"] == 0
    assert result["unknown"] == 1
