"""Behavior hashing and equivalence checks for transformed functions."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import textwrap
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class BehaviorObservation:
    outcome: str
    value: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    effects: dict[str, Any] | None = None


EffectCollector = Callable[[], Any]
_SAFE_EFFECT_EXPRESSION_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def validate_effect_expression(effect_expression: str | None) -> None:
    if effect_expression and not _SAFE_EFFECT_EXPRESSION_RE.fullmatch(effect_expression):
        raise ValueError(
            "effect_expression must be a plain name or dotted attribute path"
        )


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
    return _capture(func, args, kwargs, effect_collectors)


def _capture(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    effect_collectors: dict[str, EffectCollector] | None,
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
    except (Exception, SystemExit) as exc:
        effects["stdout"] = stdout_buf.getvalue()
        effects["stderr"] = stderr_buf.getvalue()
        for name, collector in (effect_collectors or {}).items():
            effects[name] = collector()
        # SystemExit(0) and SystemExit("0") print the same text but exit differently.
        message = (
            f"SystemExit({exc.code!r}):{exc}" if isinstance(exc, SystemExit) else str(exc)
        )
        return BehaviorObservation(
            "raise",
            exception_type=exc.__class__.__qualname__,
            exception_message=message,
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
        _capture(fn, args, kwargs, effect_collectors) for args, kwargs in inputs
    ]
    return _digest(observations)


def _default_equivalent(left: Any, right: Any) -> bool:
    return type(left) is type(right) and bool(left == right)


def _pristine_copy(
    index: int, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Deep copy of one case, taken before the original runs, for the transformed run.

    The original runs on the objects the caller supplied (identity checks against
    outside objects behave as they would for real); the transformed function runs on a
    pristine copy so neither can observe the other's mutations. A case that cannot be
    copied cannot be verified fairly, so it is rejected instead of silently shared.
    """
    try:
        return copy.deepcopy((args, kwargs))
    except Exception as exc:
        raise ValueError(
            f"test input #{index} cannot be deep-copied ({exc}); supply an independent "
            "input for each run"
        ) from exc


def assert_equivalent(
    original_func: Callable[..., Any],
    flattened_func: Callable[..., Any],
    test_inputs: list[tuple[tuple[Any, ...], dict[str, Any]]],
    *,
    equivalent: Callable[[Any, Any], bool] | None = None,
    effect_collectors: dict[str, EffectCollector] | None = None,
) -> None:
    value_equivalent = equivalent or _default_equivalent
    if not test_inputs:
        raise ValueError("assert_equivalent requires at least one test input; got none")
    for index, (args, kwargs) in enumerate(test_inputs):
        transformed_args, transformed_kwargs = _pristine_copy(index, args, kwargs)
        original = _capture(original_func, args, kwargs, effect_collectors)
        transformed = _capture(
            flattened_func, transformed_args, transformed_kwargs, effect_collectors
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
    if not cases:
        raise ValueError("assert_modules_equivalent_subprocess requires at least one case")
    validate_effect_expression(effect_expression)
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
    for index, (original, rewritten) in enumerate(zip(original_results, rewritten_results)):
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

        params = json.loads(sys.stdin.read())
        module_path = params["module_path"]
        entry_name = params["entry_name"]
        case = params["case"]
        effect_expression = params["effect_expression"]
        seed = params["seed"]
        if seed is not None:
            random.seed(seed)

        def resolve_effect(root, expression):
            if not expression:
                return None
            first, *rest = expression.split(".")
            value = vars(root)[first]
            for part in rest:
                value = getattr(value, part)
            return value

        spec = importlib.util.spec_from_file_location("_flatten_verify_target", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, entry_name)
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
                "effects": resolve_effect(module, effect_expression),
            }
        except Exception as exc:
            payload = {
                "outcome": "raise",
                "exception_type": exc.__class__.__qualname__,
                "exception_message": str(exc),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "effects": resolve_effect(module, effect_expression),
            }
        print(json.dumps(payload, sort_keys=True))
        """
    )
    stdin_payload = json.dumps({
        "module_path": str(module_path.resolve()),
        "entry_name": entry_name,
        "case": case,
        "effect_expression": effect_expression or "",
        "seed": seed,
    })
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=stdin_payload,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"verification subprocess timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocess exited with code {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise AssertionError("verification subprocess returned non-object JSON")
    return payload
