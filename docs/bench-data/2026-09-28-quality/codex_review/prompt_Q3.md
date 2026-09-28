# 코드 리뷰 요청 (읽기 전용)

아래는 같은 과제를 서로 독립적으로 수행한 6개의 변경(diff)이다. 저장소에 접근하거나 git 명령을 실행하지 말고, 이 문서에 들어 있는 내용만 근거로 판단해라. 결함 목록은 주지 않는다 — 무엇을 볼지는 네가 정하라.

## 과제 원문

리팩토링: `src/flatten/harness.py` 의 `capture_behavior` 는 정상 종료 경로와 예외 경로에서 stdout/stderr 와 effect collector 수집 코드가 중복된다. 동작은 정확히 그대로 두고(공개 시그니처, 반환값, effect 딕셔너리 키 순서, collector 호출 방식 포함) 중복을 제거해라. 기존 테스트가 모두 통과해야 하고, 동작 보존을 확인하는 테스트가 필요하면 tests/ 아래에 추가해라. 저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. 질문하지 말고 끝까지 진행해. 커밋은 하지 마.

## 변경 전 소스 (참고)

### src/flatten/harness.py
```python
"""Behavior hashing and equivalence checks for transformed functions."""

from __future__ import annotations

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

```

## 변경 6개

### R1
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..d6ddf8f 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -77,25 +77,27 @@ def capture_behavior(
     stdout_buf = StringIO()
     stderr_buf = StringIO()
     effects: dict[str, Any] = {}
+    result: Any = None
+    caught: Exception | None = None
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
-        return BehaviorObservation("return", value=result, effects=effects)
     except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+        caught = exc
+
+    effects["stdout"] = stdout_buf.getvalue()
+    effects["stderr"] = stderr_buf.getvalue()
+    for name, collector in (effect_collectors or {}).items():
+        effects[name] = collector()
+
+    if caught is not None:
         return BehaviorObservation(
             "raise",
-            exception_type=exc.__class__.__qualname__,
-            exception_message=str(exc),
+            exception_type=caught.__class__.__qualname__,
+            exception_message=str(caught),
             effects=effects,
         )
+    return BehaviorObservation("return", value=result, effects=effects)
 
 
 def capture_side_effects(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..a2dbcb4 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -76,6 +76,47 @@ def test_assert_equivalent_compares_exceptions_by_type_and_message():
     assert_equivalent(original, transformed, [((), {})])
 
 
+def test_capture_behavior_collects_effects_on_return_path():
+    calls = []
+
+    def collector():
+        calls.append(1)
+        return len(calls)
+
+    def func(value):
+        print("out")
+        return value + 1
+
+    observation = capture_behavior(func, 1, effect_collectors={"count": collector})
+
+    assert observation.outcome == "return"
+    assert observation.value == 2
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "count"]
+    assert observation.effects["stdout"] == "out\n"
+    assert observation.effects["count"] == 1
+
+
+def test_capture_behavior_collects_effects_on_raise_path():
+    calls = []
+
+    def collector():
+        calls.append(1)
+        return len(calls)
+
+    def func():
+        print("out")
+        raise ValueError("boom")
+
+    observation = capture_behavior(func, effect_collectors={"count": collector})
+
+    assert observation.outcome == "raise"
+    assert observation.exception_type == "ValueError"
+    assert observation.exception_message == "boom"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "count"]
+    assert observation.effects["stdout"] == "out\n"
+    assert observation.effects["count"] == 1
+
+
 def test_assert_equivalent_accepts_custom_equivalence_function():
     def original():
         return {"items": [1, 2]}

```

### R2
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..affb68d 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -68,6 +68,20 @@ def hash_return(val: Any) -> str:
     return _digest(val)
 
 
+def _collect_effects(
+    stdout_buf: StringIO,
+    stderr_buf: StringIO,
+    effect_collectors: dict[str, EffectCollector] | None,
+) -> dict[str, Any]:
+    effects: dict[str, Any] = {
+        "stdout": stdout_buf.getvalue(),
+        "stderr": stderr_buf.getvalue(),
+    }
+    for name, collector in (effect_collectors or {}).items():
+        effects[name] = collector()
+    return effects
+
+
 def capture_behavior(
     func: Callable[..., Any],
     *args: Any,
@@ -76,26 +90,21 @@ def capture_behavior(
 ) -> BehaviorObservation:
     stdout_buf = StringIO()
     stderr_buf = StringIO()
-    effects: dict[str, Any] = {}
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
-        return BehaviorObservation("return", value=result, effects=effects)
     except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
         return BehaviorObservation(
             "raise",
             exception_type=exc.__class__.__qualname__,
             exception_message=str(exc),
-            effects=effects,
+            effects=_collect_effects(stdout_buf, stderr_buf, effect_collectors),
         )
+    return BehaviorObservation(
+        "return",
+        value=result,
+        effects=_collect_effects(stdout_buf, stderr_buf, effect_collectors),
+    )
 
 
 def capture_side_effects(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..a3e4ea8 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -76,6 +76,34 @@ def test_assert_equivalent_compares_exceptions_by_type_and_message():
     assert_equivalent(original, transformed, [((), {})])
 
 
+def test_capture_behavior_collects_effects_on_return_and_raise_alike():
+    calls = []
+
+    def collector():
+        calls.append(1)
+        return len(calls)
+
+    def ok():
+        print("out", end="")
+        return 1
+
+    def boom():
+        print("out", end="")
+        raise ValueError("bad")
+
+    ok_obs = capture_behavior(ok, effect_collectors={"count": collector})
+    assert ok_obs.outcome == "return"
+    assert list(ok_obs.effects.keys()) == ["stdout", "stderr", "count"]
+    assert ok_obs.effects["stdout"] == "out"
+    assert ok_obs.effects["count"] == 1
+
+    raise_obs = capture_behavior(boom, effect_collectors={"count": collector})
+    assert raise_obs.outcome == "raise"
+    assert list(raise_obs.effects.keys()) == ["stdout", "stderr", "count"]
+    assert raise_obs.effects["stdout"] == "out"
+    assert raise_obs.effects["count"] == 2
+
+
 def test_assert_equivalent_accepts_custom_equivalence_function():
     def original():
         return {"items": [1, 2]}

```

### R3
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..e1d06e8 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -68,6 +68,20 @@ def hash_return(val: Any) -> str:
     return _digest(val)
 
 
+def _capture_effects(
+    stdout_buf: StringIO,
+    stderr_buf: StringIO,
+    effect_collectors: dict[str, EffectCollector] | None,
+) -> dict[str, Any]:
+    effects: dict[str, Any] = {
+        "stdout": stdout_buf.getvalue(),
+        "stderr": stderr_buf.getvalue(),
+    }
+    for name, collector in (effect_collectors or {}).items():
+        effects[name] = collector()
+    return effects
+
+
 def capture_behavior(
     func: Callable[..., Any],
     *args: Any,
@@ -76,20 +90,13 @@ def capture_behavior(
 ) -> BehaviorObservation:
     stdout_buf = StringIO()
     stderr_buf = StringIO()
-    effects: dict[str, Any] = {}
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+        effects = _capture_effects(stdout_buf, stderr_buf, effect_collectors)
         return BehaviorObservation("return", value=result, effects=effects)
     except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+        effects = _capture_effects(stdout_buf, stderr_buf, effect_collectors)
         return BehaviorObservation(
             "raise",
             exception_type=exc.__class__.__qualname__,
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..b069ddc 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -76,6 +76,53 @@ def test_assert_equivalent_compares_exceptions_by_type_and_message():
     assert_equivalent(original, transformed, [((), {})])
 
 
+def test_capture_behavior_return_path_collects_effects_in_order():
+    def func(value):
+        print("out", end="")
+        return value
+
+    observation = capture_behavior(
+        func,
+        1,
+        effect_collectors={"counter": lambda: "counter-value"},
+    )
+
+    assert observation.outcome == "return"
+    assert observation.value == 1
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "counter"]
+    assert observation.effects["stdout"] == "out"
+    assert observation.effects["counter"] == "counter-value"
+
+
+def test_capture_behavior_raise_path_collects_effects_in_order():
+    def func():
+        print("out", end="")
+        raise ValueError("boom")
+
+    observation = capture_behavior(
+        func,
+        effect_collectors={"counter": lambda: "counter-value"},
+    )
+
+    assert observation.outcome == "raise"
+    assert observation.exception_type == "ValueError"
+    assert observation.exception_message == "boom"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "counter"]
+    assert observation.effects["stdout"] == "out"
+    assert observation.effects["counter"] == "counter-value"
+
+
+def test_capture_behavior_collector_error_after_successful_call_propagates():
+    def func():
+        return "ok"
+
+    def failing_collector():
+        raise RuntimeError("collector failed")
+
+    with pytest.raises(RuntimeError, match="collector failed"):
+        capture_behavior(func, effect_collectors={"bad": failing_collector})
+
+
 def test_assert_equivalent_accepts_custom_equivalence_function():
     def original():
         return {"items": [1, 2]}

```

### R4
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..50481ae 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -68,6 +68,20 @@ def hash_return(val: Any) -> str:
     return _digest(val)
 
 
+def _collect_effects(
+    stdout_buf: StringIO,
+    stderr_buf: StringIO,
+    effect_collectors: dict[str, EffectCollector] | None,
+) -> dict[str, Any]:
+    effects: dict[str, Any] = {
+        "stdout": stdout_buf.getvalue(),
+        "stderr": stderr_buf.getvalue(),
+    }
+    for name, collector in (effect_collectors or {}).items():
+        effects[name] = collector()
+    return effects
+
+
 def capture_behavior(
     func: Callable[..., Any],
     *args: Any,
@@ -76,26 +90,23 @@ def capture_behavior(
 ) -> BehaviorObservation:
     stdout_buf = StringIO()
     stderr_buf = StringIO()
-    effects: dict[str, Any] = {}
+    result: Any = None
+    exc: Exception | None = None
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
-        return BehaviorObservation("return", value=result, effects=effects)
-    except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+    except Exception as caught:
+        exc = caught
+
+    effects = _collect_effects(stdout_buf, stderr_buf, effect_collectors)
+    if exc is not None:
         return BehaviorObservation(
             "raise",
             exception_type=exc.__class__.__qualname__,
             exception_message=str(exc),
             effects=effects,
         )
+    return BehaviorObservation("return", value=result, effects=effects)
 
 
 def capture_side_effects(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..83d62aa 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -76,6 +76,75 @@ def test_assert_equivalent_compares_exceptions_by_type_and_message():
     assert_equivalent(original, transformed, [((), {})])
 
 
+def test_capture_behavior_effects_key_order_on_return():
+    calls = []
+
+    def collector_a():
+        calls.append("a")
+        return "a-value"
+
+    def collector_b():
+        calls.append("b")
+        return "b-value"
+
+    observation = capture_behavior(
+        lambda: "ok",
+        effect_collectors={"custom_a": collector_a, "custom_b": collector_b},
+    )
+
+    assert observation.outcome == "return"
+    assert observation.value == "ok"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "custom_a", "custom_b"]
+    assert observation.effects["custom_a"] == "a-value"
+    assert observation.effects["custom_b"] == "b-value"
+    assert calls == ["a", "b"]
+
+
+def test_capture_behavior_effects_key_order_on_raise():
+    calls = []
+
+    def collector_a():
+        calls.append("a")
+        return "a-value"
+
+    def collector_b():
+        calls.append("b")
+        return "b-value"
+
+    def raises():
+        raise ValueError("boom")
+
+    observation = capture_behavior(
+        raises,
+        effect_collectors={"custom_a": collector_a, "custom_b": collector_b},
+    )
+
+    assert observation.outcome == "raise"
+    assert observation.exception_type == "ValueError"
+    assert observation.exception_message == "boom"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "custom_a", "custom_b"]
+    assert calls == ["a", "b"]
+
+
+def test_capture_behavior_collectors_called_exactly_once():
+    call_count = {"n": 0}
+
+    def collector():
+        call_count["n"] += 1
+        return call_count["n"]
+
+    capture_behavior(lambda: None, effect_collectors={"count": collector})
+    assert call_count["n"] == 1
+
+    call_count["n"] = 0
+
+    def raises():
+        raise RuntimeError("x")
+
+    capture_behavior(raises, effect_collectors={"count": collector})
+    assert call_count["n"] == 1
+
+
 def test_assert_equivalent_accepts_custom_equivalence_function():
     def original():
         return {"items": [1, 2]}

```

### R5
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..9ab340c 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -76,26 +76,27 @@ def capture_behavior(
 ) -> BehaviorObservation:
     stdout_buf = StringIO()
     stderr_buf = StringIO()
-    effects: dict[str, Any] = {}
+
+    def _collect_effects() -> dict[str, Any]:
+        effects: dict[str, Any] = {
+            "stdout": stdout_buf.getvalue(),
+            "stderr": stderr_buf.getvalue(),
+        }
+        for name, collector in (effect_collectors or {}).items():
+            effects[name] = collector()
+        return effects
+
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
-        return BehaviorObservation("return", value=result, effects=effects)
     except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
         return BehaviorObservation(
             "raise",
             exception_type=exc.__class__.__qualname__,
             exception_message=str(exc),
-            effects=effects,
+            effects=_collect_effects(),
         )
+    return BehaviorObservation("return", value=result, effects=_collect_effects())
 
 
 def capture_side_effects(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, str]:
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..72dbd6e 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -89,3 +89,47 @@ def test_assert_equivalent_accepts_custom_equivalence_function():
         [((), {})],
         equivalent=lambda left, right: list(left["items"]) == list(right["items"]),
     )
+
+
+def test_capture_behavior_collects_effects_on_return():
+    calls = []
+
+    def collector():
+        calls.append("called")
+        return len(calls)
+
+    def func():
+        print("out", end="")
+        return "ok"
+
+    observation = capture_behavior(func, effect_collectors={"count": collector})
+
+    assert observation.outcome == "return"
+    assert observation.value == "ok"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "count"]
+    assert observation.effects["stdout"] == "out"
+    assert observation.effects["stderr"] == ""
+    assert observation.effects["count"] == 1
+    assert calls == ["called"]
+
+
+def test_capture_behavior_collects_effects_on_raise():
+    calls = []
+
+    def collector():
+        calls.append("called")
+        return len(calls)
+
+    def func():
+        print("out", end="")
+        raise ValueError("boom")
+
+    observation = capture_behavior(func, effect_collectors={"count": collector})
+
+    assert observation.outcome == "raise"
+    assert observation.exception_type == "ValueError"
+    assert observation.exception_message == "boom"
+    assert list(observation.effects.keys()) == ["stdout", "stderr", "count"]
+    assert observation.effects["stdout"] == "out"
+    assert observation.effects["count"] == 1
+    assert calls == ["called"]

```

### R6
```diff
diff --git a/src/flatten/harness.py b/src/flatten/harness.py
index 5ee0712..5e3f7b0 100644
--- a/src/flatten/harness.py
+++ b/src/flatten/harness.py
@@ -68,6 +68,18 @@ def hash_return(val: Any) -> str:
     return _digest(val)
 
 
+def _collect_effects(
+    effects: dict[str, Any],
+    stdout_buf: StringIO,
+    stderr_buf: StringIO,
+    effect_collectors: dict[str, EffectCollector] | None,
+) -> None:
+    effects["stdout"] = stdout_buf.getvalue()
+    effects["stderr"] = stderr_buf.getvalue()
+    for name, collector in (effect_collectors or {}).items():
+        effects[name] = collector()
+
+
 def capture_behavior(
     func: Callable[..., Any],
     *args: Any,
@@ -80,16 +92,10 @@ def capture_behavior(
     try:
         with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
             result = func(*args, **kwargs)
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+        _collect_effects(effects, stdout_buf, stderr_buf, effect_collectors)
         return BehaviorObservation("return", value=result, effects=effects)
     except Exception as exc:
-        effects["stdout"] = stdout_buf.getvalue()
-        effects["stderr"] = stderr_buf.getvalue()
-        for name, collector in (effect_collectors or {}).items():
-            effects[name] = collector()
+        _collect_effects(effects, stdout_buf, stderr_buf, effect_collectors)
         return BehaviorObservation(
             "raise",
             exception_type=exc.__class__.__qualname__,
diff --git a/tests/test_harness.py b/tests/test_harness.py
index d1b56ba..381e376 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -1,6 +1,6 @@
 ﻿import pytest
 
-from flatten.harness import assert_equivalent, compute_behavior_hash
+from flatten.harness import assert_equivalent, capture_behavior, compute_behavior_hash
 
 
 def test_compute_behavior_hash_is_stable_for_same_behavior():
@@ -89,3 +89,21 @@ def test_assert_equivalent_accepts_custom_equivalence_function():
         [((), {})],
         equivalent=lambda left, right: list(left["items"]) == list(right["items"]),
     )
+
+
+def test_capture_behavior_runs_effect_collectors_on_return():
+    observation = capture_behavior(
+        lambda: 42, effect_collectors={"calls": lambda: "collected"}
+    )
+    assert observation.outcome == "return"
+    assert observation.effects == {"stdout": "", "stderr": "", "calls": "collected"}
+    assert list(observation.effects) == ["stdout", "stderr", "calls"]
+
+
+def test_capture_behavior_runs_effect_collectors_on_raise():
+    def boom():
+        raise ValueError("bad")
+
+    observation = capture_behavior(boom, effect_collectors={"calls": lambda: "collected"})
+    assert observation.outcome == "raise"
+    assert observation.effects == {"stdout": "", "stderr": "", "calls": "collected"}

```

## 요청

각 변경(R1~R6)을 **독립적으로** 적대적으로 리뷰해라. 다른 변경과 비교해 점수를 상대평가하지 말고, 각각을 스펙(과제 원문) 대비 절대 기준으로 본다.

각 변경마다 다음을 JSON 으로 내라 (전체를 하나의 JSON 객체, 키는 R1..R6):
- `defects`: 결함 목록. 항목마다 `severity`("high"|"medium"|"low"), `kind`("correctness"|"spec_mismatch"|"edge_case"|"behavior_change"|"test_weakness"|"unneeded_change"|"other"), `description`(한두 문장, diff 의 어느 부분인지 명시)
- `spec_met`: true/false — 과제 원문의 요구를 빠짐없이 충족하는가
- `scores`: `correctness`, `minimality`(불필요한 변경 없이 최소인가), `test_quality`, 각 1~5 정수
- `verdict`: 한 문장

결함이 없으면 `defects` 는 빈 배열로 둬라. 근거 없는 지적은 하지 마라. 출력은 JSON 하나만, 앞뒤 설명 없이.
