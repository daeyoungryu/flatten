"""동등성 검증 — 반환값 + 부수효과 해시 비교."""

from __future__ import annotations

import hashlib
import pickle
import sys
from io import StringIO
from typing import Any, Callable
from unittest.mock import patch


def hash_return(val: Any) -> str:
    try:
        return hashlib.sha256(pickle.dumps(val)).hexdigest()
    except Exception:
        return hashlib.sha256(repr(val).encode()).hexdigest()


def capture_side_effects(func: Callable, *args, **kwargs) -> tuple[Any, str]:
    stdout_buf = StringIO()
    with patch("sys.stdout", stdout_buf):
        result = func(*args, **kwargs)
    return result, stdout_buf.getvalue()


def assert_equivalent(
    original_func: Callable,
    flattened_func: Callable,
    test_inputs: list[tuple[tuple, dict]],
) -> None:
    """원본과 변환된 함수가 모든 입력에 대해 동등한지 검증한다."""
    for args, kwargs in test_inputs:
        orig_ret, orig_side = capture_side_effects(original_func, *args, **kwargs)
        flat_ret, flat_side = capture_side_effects(flattened_func, *args, **kwargs)

        orig_hash = hash_return(orig_ret)
        flat_hash = hash_return(flat_ret)

        if orig_hash != flat_hash:
            raise AssertionError(
                f"반환값 불일치:\n  원본: {orig_ret!r}\n  변환: {flat_ret!r}"
            )
        if orig_side != flat_side:
            raise AssertionError(
                f"부수효과 불일치:\n  원본: {orig_side!r}\n  변환: {flat_side!r}"
            )
