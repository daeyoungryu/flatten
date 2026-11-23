"""Shared internal utilities for flatten."""

from __future__ import annotations

import functools
import os
import shutil
import tempfile
from pathlib import Path


@functools.lru_cache(maxsize=512)
def _resolve_cached(filename: str, cwd: str) -> str:
    # ``cwd`` is part of the cache key: a relative name must not keep resolving to the
    # directory it was first seen in after the process changes directory.
    return str(Path(filename).resolve()).replace("\\", "/")


def normalize_filename(filename: str) -> str:
    """Return the resolved absolute path string; pass through empty or virtual paths unchanged."""
    if not filename or filename.startswith("<"):
        return filename
    return _resolve_cached(filename, os.getcwd())


def stage_text(target: Path, text: str) -> tuple[Path, Path]:
    """Write ``text`` to a fresh private directory next to ``target``.

    The staged file keeps the basename of ``target`` (code that inspects ``__file__``
    sees the published name) while the unique directory can never collide with an
    existing file. Returns ``(stage_dir, staged_file)``; call :func:`discard_stage`
    when done.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".flatten-stage-", dir=target.parent))
    staged = stage_dir / target.name
    try:
        staged.write_text(text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    return stage_dir, staged


def discard_stage(stage_dir: Path) -> None:
    shutil.rmtree(stage_dir, ignore_errors=True)
