from pathlib import Path


def test_si_gate_output_literals_are_ascii_safe() -> None:
    text = Path("scripts/si_gate.py").read_text(encoding="utf-8")
    non_ascii = sorted({f"U+{ord(ch):04X}" for ch in text if ord(ch) > 127})

    assert non_ascii == []
