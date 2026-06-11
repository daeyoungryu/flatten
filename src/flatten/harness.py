"""Behavior hashing and equivalence checks for transformed functions."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BehaviorObservation:
    outcome: str
    value: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    effects: dict[str, Any] | None = None


EffectCollector = Callable[[], Any]


def _jsonable(value: Any, _seen: set[int] | None = None) -> Any:
    seen = _seen if _seen is not None else set()
    if isinstance(value, (list, tuple, dict)) or hasattr(value, "__dict__"):
        value_id = id(value)
        if value_id in seen:
            return "<cycle>"
        seen.add(value_id)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, seen) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item, seen)
            for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if hasattr(value, "__dict__"):
        return {
            "__class__": value.__class__.__qualname__,
            "state": _jsonable(vars(value), seen),
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
    stderr_buf = StringIO()
    effects: dict[str, Any] = {}
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            result = func(*args, **kwargs)
        effects["stdout"] = stdout_buf.getvalue()
        effects["stderr"] = stderr_buf.getvalue()
        for name, collector in (effect_collectors or {}).items():
            effects[name] = collector()
        return BehaviorObservation("return", value=result, effects=effects)
    except Exception as exc:
        effects["stdout"] = stdout_buf.getvalue()
        effects["stderr"] = stderr_buf.getvalue()
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


def assert_modules_equivalent_subprocess(
    original_path: Path,
    rewritten_path: Path,
    entry_name: str,
    *,
    cases: list[dict[str, Any]],
    effect_expression: str | None = None,
    timeout: float = 5.0,
    seed: int | None = None,
) -> dict[str, Any]:
    """Compare module entry behavior in isolated subprocesses."""
    original_results = [
        _run_module_case_subprocess(
            original_path,
            entry_name,
            case,
            effect_expression=effect_expression,
            timeout=timeout,
            seed=seed,
        )
        for case in cases
    ]
    rewritten_results = [
        _run_module_case_subprocess(
            rewritten_path,
            entry_name,
            case,
            effect_expression=effect_expression,
            timeout=timeout,
            seed=seed,
        )
        for case in cases
    ]
    for index, (original, rewritten) in enumerate(
        zip(original_results, rewritten_results, strict=True)
    ):
        if original != rewritten:
            if original.get("outcome") == "raise" or rewritten.get("outcome") == "raise":
                raise AssertionError(
                    f"input #{index} exception divergence: original={original!r}; "
                    f"transformed={rewritten!r}"
                )
            raise AssertionError(
                f"input #{index} behavior divergence: original={original!r}; "
                f"transformed={rewritten!r}"
            )
    return {
        "equivalent": True,
        "cases": len(cases),
        "seed": seed,
        "verification_limit": "observed inputs only; not proof",
    }


def _run_module_case_subprocess(
    module_path: Path,
    entry_name: str,
    case: dict[str, Any],
    *,
    effect_expression: str | None,
    timeout: float,
    seed: int | None,
) -> dict[str, Any]:
    script = textwrap.dedent(
        """
        import contextlib
        import importlib.util
        import io
        import json
        import random
        import sys

        module_path, entry_name, case_json, effect_expression, seed_json = sys.argv[1:6]
        seed = json.loads(seed_json)
        if seed is not None:
            random.seed(seed)
        spec = importlib.util.spec_from_file_location("_flatten_verify_target", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        fn = getattr(module, entry_name)
        case = json.loads(case_json)
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                value = fn(*case.get("args", []), **case.get("kwargs", {}))
            payload = {
                "outcome": "return",
                "value": value,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "effects": eval(effect_expression, vars(module)) if effect_expression else None,
            }
        except Exception as exc:
            payload = {
                "outcome": "raise",
                "exception_type": exc.__class__.__qualname__,
                "exception_message": str(exc),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "effects": eval(effect_expression, vars(module)) if effect_expression else None,
            }
        print(json.dumps(payload, sort_keys=True))
        """
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(module_path.resolve()),
                entry_name,
                json.dumps(case),
                effect_expression or "",
                json.dumps(seed),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"verification subprocess timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError("verification subprocess returned non-object JSON")
    return payload
