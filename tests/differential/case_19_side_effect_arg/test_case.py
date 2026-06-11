from pathlib import Path


def test_fixture_exists():
    assert (Path(__file__).parent / "input.py").exists()
