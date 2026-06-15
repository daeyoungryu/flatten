"""Shared internal utilities for flatten."""

from __future__ import annotations

from pathlib import Path


def normalize_filename(filename: str) -> str:
    """Return the resolved absolute path string; pass through empty or virtual paths unchanged."""
    if not filename or filename.startswith("<"):
        return filename
    return str(Path(filename).resolve()).replace("\\", "/")
