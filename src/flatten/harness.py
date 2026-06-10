"""Behavior hashing and equivalence checks for transformed functions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from typing import Any
from unittest.mock import patch


@dataclass(frozen=True)
class BehaviorObservation:
    outcome: str
    value: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    effects: dict[str, Any] | None = None


EffectCollector = Callable[[], Any]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if hasattr(value, "__dict__"):
        return {
            "__class__": value.__class__.__qualname__,
            "state": _jsonable(vars(value)),
        }
    return {"__class__": value.__class__.__qualname__}


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_return(val: Any) -> str:
    return _digest(val)


def capture_behavior(
    func: Callable[..., Any],
    *args: Any,
    effect_collectors: dict[str, EffectCollector] | None = None,
    **kwargs: Any,
) -> BehaviorObservation:
    stdout_buf = StringIO()
    effects: dict[str, Any] = {}
    try:
        with patch("sys.stdout", stdout_buf):
            result = func(*args, **kwargs)
        effects["stdout"] = stdout_buf.getvalue()
        for name, collector in (effect_collectors or {}).items():
            effects[name] = collector()
        return BehaviorObservation("return", value=result, effects=effects)
    except Exception as exc:
        effects["stdout"] = stdout_buf.getvalue()
        for name, collector in (effect_collectors or {}).items():
            effects[name] = collector()
        return BehaviorObservation(
            "raise",
            exception_type=exc.__class__.__qualname__,
            exception_message=str(exc),
            effects=effects,
        )


def capture_side_effects(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
    observation = capture_behavior(func, *args, **kwargs)
    if observation.outcome == "raise":
        raise RuntimeError(
            f"{observation.exception_type}: {observation.exception_message}"
        )
    return observation.value, (observation.effects or {}).get("stdout", "")


def compute_behavior_hash(
    fn: Callable[..., Any],
    inputs: list[tuple[tuple[Any, ...], dict[str, Any]]],
    *,
    effect_collectors: dict[str, EffectCollector] | None = None,
) -> str:
    observations = [
        capture_behavior(fn, *args, effect_collectors=effect_collectors, **kwargs)
        for args, kwargs in inputs
    ]
    return _digest(observations)


def _default_equivalent(left: Any, right: Any) -> bool:
    return bool(left == right)


def assert_equivalent(
    original_func: Callable[..., Any],
    flattened_func: Callable[..., Any],
    test_inputs: list[tuple[tuple[Any, ...], dict[str, Any]]],
    *,
    equivalent: Callable[[Any, Any], bool] | None = None,
    effect_collectors: dict[str, EffectCollector] | None = None,
) -> None:
    value_equivalent = equivalent or _default_equivalent
    for index, (args, kwargs) in enumerate(test_inputs):
        original = capture_behavior(
            original_func, *args, effect_collectors=effect_collectors, **kwargs
        )
        transformed = capture_behavior(
            flattened_func, *args, effect_collectors=effect_collectors, **kwargs
        )

        if original.outcome != transformed.outcome:
            raise AssertionError(
                f"input #{index} outcome divergence: original={original!r}; "
                f"transformed={transformed!r}"
            )
        if original.outcome == "raise":
            if (
                original.exception_type,
                original.exception_message,
            ) != (
                transformed.exception_type,
                transformed.exception_message,
            ):
                raise AssertionError(
                    f"input #{index} exception divergence: original={original!r}; "
                    f"transformed={transformed!r}"
                )
        elif not value_equivalent(original.value, transformed.value):
            raise AssertionError(
                f"input #{index} return divergence: original={original.value!r}; "
                f"transformed={transformed.value!r}"
            )
        if original.effects != transformed.effects:
            raise AssertionError(
                f"input #{index} effects divergence: original={original.effects!r}; "
                f"transformed={transformed.effects!r}"
            )
