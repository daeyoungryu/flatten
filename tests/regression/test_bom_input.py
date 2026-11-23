"""Regression: source files saved with a UTF-8 BOM must be readable by the CLI."""

import json

from flatten._cli_io import _read
from flatten.cli import main

SOURCE = (
    "class Worker:\n"
    "    def run(self, value):\n"
    "        return value + 1\n"
    "\n"
    "\n"
    "def main():\n"
    "    return Worker().run(2)\n"
)


def test_read_strips_utf8_bom(tmp_path):
    path = tmp_path / "bom.py"
    path.write_bytes(b"\xef\xbb\xbf" + SOURCE.encode("utf-8"))

    assert _read(path) == SOURCE


def test_read_without_bom_is_unchanged(tmp_path):
    path = tmp_path / "plain.py"
    path.write_bytes(SOURCE.encode("utf-8"))

    assert _read(path) == SOURCE


def test_analyze_accepts_bom_source(tmp_path, capsys):
    path = tmp_path / "bom_case.py"
    path.write_bytes(b"\xef\xbb\xbf" + SOURCE.encode("utf-8"))

    assert main(["analyze", path.as_posix(), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"] == []
    assert len(payload["call_sites"]) == 1


def test_specialize_args_json_accepts_bom(tmp_path):
    from flatten.specialize import load_args_json

    path = tmp_path / "args.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{"args": [1, 2], "kwargs": {"k": 3}}')

    assert load_args_json(path) == ((1, 2), {"k": 3})


def test_benchmark_catalog_accepts_bom(tmp_path):
    from flatten.benchmarks import load_benchmark_catalog

    path = tmp_path / "projects.csv"
    path.write_bytes(
        b"\xef\xbb\xbfname,package,repo_url,category\r\n"
        b"demo,demo,https://example.invalid/demo,lib\r\n"
    )

    projects = load_benchmark_catalog(path)

    assert [p.name for p in projects] == ["demo"]
