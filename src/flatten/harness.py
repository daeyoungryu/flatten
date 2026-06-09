"""Behavior hashing and equivalence checks for transformed functions."""

from __future__ import annotations

import hashlib
import pickle
from io import StringIO
from typing import Any, Callable
from unittest.mock import patch


def _stable_bytes(value: Any) -> bytes:
    try:
        return pickle.dumps(value)
    except Exception:
        return repr(value).encode("utf-8", errors="replace")


def hash_return(val: Any) -> str:
    return hashlib.sha256(_stable_bytes(val)).hexdigest()


def capture_side_effects(func: Callable, *args, **kwargs) -> tuple[Any, str]:
    stdout_buf = StringIO()
    with patch("sys.stdout", stdout_buf):
        result = func(*args, **kwargs)
    return result, stdout_buf.getvalue()


def compute_behavior_hash(
    fn: Callable,
    inputs: list[tuple[tuple, dict]],
) -> str:
    observations = []
    for args, kwargs in inputs:
        try:
            return_value, stdout = capture_side_effects(fn, *args, **kwargs)
            observations.append(("return", return_value, stdout))
        except Exception as exc:
            observations.append(("raise", exc.__class__.__qualname__, str(exc)))
    return hashlib.sha256(_stable_bytes(observations)).hexdigest()


def assert_equivalent(
    original_func: Callable,
    flattened_func: Callable,
    test_inputs: list[tuple[tuple, dict]],
) -> None:
    for index, (args, kwargs) in enumerate(test_inputs):
        orig_ret, orig_stdout = capture_side_effects(original_func, *args, **kwargs)
        flat_ret, flat_stdout = capture_side_effects(flattened_func, *args, **kwargs)

        if hash_return(orig_ret) != hash_return(flat_ret):
            raise AssertionError(
                "input #{index} return divergence: original={orig!r}; "
                "transformed={flat!r}".format(
                    index=index,
                    orig=orig_ret,
                    flat=flat_ret,
                )
            )
        if orig_stdout != flat_stdout:
            raise AssertionError(
                "input #{index} stdout divergence: original={orig!r}; "
                "transformed={flat!r}".format(
                    index=index,
                    orig=orig_stdout,
                    flat=flat_stdout,
                )
            )
