# 코드 리뷰 요청 (읽기 전용)

아래는 같은 과제를 서로 독립적으로 수행한 6개의 변경(diff)이다. 저장소에 접근하거나 git 명령을 실행하지 말고, 이 문서에 들어 있는 내용만 근거로 판단해라. 결함 목록은 주지 않는다 — 무엇을 볼지는 네가 정하라.

## 과제 원문

작은 기능 추가: `BehaviorComparator.compare` 에 키워드 전용 선택 인자 `max_mismatches: int | None = None` 을 추가해라. None 이면 지금 동작과 완전히 같다. 정수면 케이스를 순서대로 비교하다가 누적 불일치 수가 `max_mismatches` 이상이 되는 순간 나머지 케이스 비교를 중단한다(한 케이스에서 나온 불일치는 잘라내지 않고 모두 포함한다). 반환값의 `cases` 는 지금처럼 전체 케이스 수를 유지한다. `BehaviorComparisonResult` 에 `truncated: bool = False` 필드를 추가해, 남은 케이스를 건너뛰고 중단했을 때만 True 로 하고 `to_json()` 결과에도 `"truncated"` 키를 넣어라. `max_mismatches < 1` 이면 ValueError. tests/ 아래에 테스트를 추가하고 저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. 질문하지 말고 끝까지 진행해. 커밋은 하지 마.

## 변경 전 소스 (참고)

### src/flatten/comparator.py
```python
"""Behavior comparison API for original and rewritten callables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flatten.harness import BehaviorObservation, capture_behavior


@dataclass(frozen=True)
class BehaviorMismatch:
    """A single field mismatch between original and transformed behavior."""

    case_index: int
    field: str
    original: str
    transformed: str


@dataclass(frozen=True)
class BehaviorComparisonResult:
    """Result of comparing original and transformed callable behavior across test cases."""

    equivalent: bool
    cases: int
    mismatches: list[BehaviorMismatch]

    def to_json(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "equivalent": self.equivalent,
            "cases": self.cases,
            "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
        }


class BehaviorComparator:
    """Compare the behavior of two callables across a set of test cases."""

    def compare(
        self,
        original: Callable[..., Any],
        transformed: Callable[..., Any],
        cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
    ) -> BehaviorComparisonResult:
        mismatches: list[BehaviorMismatch] = []
        for index, (args, kwargs) in enumerate(cases):
            left = capture_behavior(original, *args, **kwargs)
            right = capture_behavior(transformed, *args, **kwargs)
            mismatches.extend(_compare_observation(index, left, right))
        return BehaviorComparisonResult(
            equivalent=not mismatches,
            cases=len(cases),
            mismatches=mismatches,
        )


def _compare_observation(
    index: int,
    original: BehaviorObservation,
    transformed: BehaviorObservation,
) -> list[BehaviorMismatch]:
    mismatches: list[BehaviorMismatch] = []
    if original.outcome != transformed.outcome:
        return [
            BehaviorMismatch(index, "outcome", original.outcome, transformed.outcome)
        ]
    if original.outcome == "raise":
        left = f"{original.exception_type}: {original.exception_message}"
        right = f"{transformed.exception_type}: {transformed.exception_message}"
        if left != right:
            mismatches.append(BehaviorMismatch(index, "exception", left, right))
    elif original.value != transformed.value:
        mismatches.append(
            BehaviorMismatch(index, "return", repr(original.value), repr(transformed.value))
        )
    if original.effects != transformed.effects:
        mismatches.append(
            BehaviorMismatch(index, "effects", repr(original.effects), repr(transformed.effects))
        )
    return mismatches

```

## 변경 6개

### R1
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..50e4bdb 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index < len(cases) - 1
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..fd5a4b5 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,66 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_default_max_mismatches_is_unbounded():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 3
+    assert result.truncated is False
+    assert result.to_json()["truncated"] is False
+
+
+def test_behavior_comparator_stops_once_max_mismatches_reached():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 2
+    assert {m.case_index for m in result.mismatches} == {0, 1}
+    assert result.truncated is True
+    assert result.to_json()["truncated"] is True
+
+
+def test_behavior_comparator_does_not_split_a_single_case_mismatches():
+    def left():
+        raise ValueError("left")
+
+    def right():
+        print("out", file=sys.stderr)
+        raise ValueError("right")
+
+    cases = [((), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.cases == 1
+    assert len(result.mismatches) == 2
+    assert result.truncated is False
+
+
+def test_behavior_comparator_max_mismatches_below_one_raises():
+    def left():
+        return 1
+
+    def right():
+        return 1
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(left, right, [((), {})], max_mismatches=0)

```

### R2
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..50e4bdb 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index < len(cases) - 1
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..7ec445c 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,79 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_max_mismatches_none_matches_default_behavior():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    default_result = BehaviorComparator().compare(left, right, cases)
+    explicit_none_result = BehaviorComparator().compare(left, right, cases, max_mismatches=None)
+
+    assert explicit_none_result.mismatches == default_result.mismatches
+    assert explicit_none_result.cases == default_result.cases
+    assert explicit_none_result.truncated is False
+
+
+def test_max_mismatches_stops_once_threshold_reached():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 2
+    assert {m.case_index for m in result.mismatches} == {0, 1}
+    assert result.truncated is True
+    assert result.to_json()["truncated"] is True
+
+
+def test_max_mismatches_does_not_cut_off_within_a_case():
+    def left(value):
+        print("out")
+        return value
+
+    def right(value):
+        print("different")
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert len(result.mismatches) == 2
+    assert {m.field for m in result.mismatches} == {"return", "effects"}
+    assert result.truncated is True
+
+
+def test_max_mismatches_not_truncated_when_threshold_never_reached():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=5)
+
+    assert result.truncated is False
+    assert result.cases == 1
+
+
+def test_max_mismatches_rejects_values_below_one():
+    def left(value):
+        return value
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(left, left, [((1,), {})], max_mismatches=0)

```

### R3
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..50e4bdb 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index < len(cases) - 1
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..df22764 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,68 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def _mismatching_pair(n):
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    return left, right, [((i,), {}) for i in range(n)]
+
+
+def test_behavior_comparator_max_mismatches_none_is_unchanged():
+    left, right, cases = _mismatching_pair(5)
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=None)
+
+    assert result.cases == 5
+    assert len(result.mismatches) == 5
+    assert result.truncated is False
+
+
+def test_behavior_comparator_stops_after_threshold_reached():
+    left, right, cases = _mismatching_pair(5)
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 5
+    assert len(result.mismatches) == 2
+    assert result.truncated is True
+    assert result.to_json()["truncated"] is True
+
+
+def test_behavior_comparator_not_truncated_when_threshold_hit_on_last_case():
+    left, right, cases = _mismatching_pair(3)
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=3)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 3
+    assert result.truncated is False
+
+
+def test_behavior_comparator_keeps_all_mismatches_from_the_stopping_case():
+    def left(value):
+        print("out")
+        return value
+
+    def right(value):
+        print("different")
+        return value + 1
+
+    cases = [((1,), {})] * 3
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert len(result.mismatches) == 2
+    assert result.truncated is True
+
+
+def test_behavior_comparator_max_mismatches_below_one_raises():
+    left, right, cases = _mismatching_pair(1)
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(left, right, cases, max_mismatches=0)

```

### R4
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..50e4bdb 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index < len(cases) - 1
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..f92a92b 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,81 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+    assert result.truncated is False
+
+
+def test_max_mismatches_none_matches_default_behavior():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    default_result = BehaviorComparator().compare(left, right, cases)
+    explicit_none_result = BehaviorComparator().compare(left, right, cases, max_mismatches=None)
+
+    assert explicit_none_result == default_result
+
+
+def test_max_mismatches_stops_after_threshold_reached():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0
+    assert result.truncated is True
+    assert result.to_json()["truncated"] is True
+
+
+def test_max_mismatches_keeps_all_mismatches_from_the_case_that_hits_threshold():
+    def left(value):
+        print("out")
+        return value
+
+    def right(value):
+        print("different")
+        return value + 1
+
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    # a single case can yield both a "return" and an "effects" mismatch;
+    # both must be kept even though max_mismatches=1 was already exceeded.
+    assert result.cases == 2
+    assert len(result.mismatches) == 2
+    assert {m.case_index for m in result.mismatches} == {0}
+    assert result.truncated is True
+
+
+def test_max_mismatches_not_reached_is_not_truncated():
+    def left(value):
+        return value
+
+    def right(value):
+        return value
+
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=5)
+
+    assert result.mismatches == []
+    assert result.truncated is False
+
+
+def test_max_mismatches_below_one_raises_value_error():
+    def noop():
+        return None
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(noop, noop, [((), {})], max_mismatches=0)

```

### R5
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..50e4bdb 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index < len(cases) - 1
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..f88e287 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,109 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def _mismatching_pair(n):
+    def left(value):
+        return value
+
+    def right(value):
+        return -value
+
+    return left, right
+
+
+def test_compare_default_truncated_is_false():
+    left, right = _mismatching_pair(1)
+    result = BehaviorComparator().compare(left, right, [((1,), {}), ((2,), {})])
+
+    assert result.truncated is False
+    assert result.cases == 2
+    assert len(result.mismatches) == 2
+
+
+def test_compare_max_mismatches_none_matches_current_behavior():
+    left, right = _mismatching_pair(1)
+    cases = [((1,), {}), ((2,), {}), ((3,), {})]
+
+    default_result = BehaviorComparator().compare(left, right, cases)
+    explicit_none_result = BehaviorComparator().compare(left, right, cases, max_mismatches=None)
+
+    assert explicit_none_result.equivalent == default_result.equivalent
+    assert explicit_none_result.cases == default_result.cases
+    assert explicit_none_result.mismatches == default_result.mismatches
+    assert explicit_none_result.truncated is False
+
+
+def test_compare_stops_early_once_max_mismatches_reached():
+    left, right = _mismatching_pair(1)
+    cases = [((1,), {}), ((2,), {}), ((3,), {}), ((4,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 4
+    assert len(result.mismatches) == 2
+    assert [m.case_index for m in result.mismatches] == [0, 1]
+    assert result.truncated is True
+
+
+def test_compare_not_truncated_when_limit_reached_on_last_case():
+    left, right = _mismatching_pair(1)
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 2
+    assert len(result.mismatches) == 2
+    assert result.truncated is False
+
+
+def test_compare_does_not_cut_mismatches_within_a_single_case():
+    def left(value):
+        print("out")
+        raise ValueError("left")
+
+    def right(value):
+        print("different")
+        raise ValueError("right")
+
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.cases == 2
+    # the first case alone produces >=2 mismatches (effects + exception),
+    # none of which should be cut off even though max_mismatches is 1
+    assert len(result.mismatches) >= 2
+    assert all(m.case_index == 0 for m in result.mismatches)
+    assert result.truncated is True
+
+
+def test_compare_max_mismatches_zero_raises_value_error():
+    left, right = _mismatching_pair(1)
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(left, right, [((1,), {})], max_mismatches=0)
+
+
+def test_compare_max_mismatches_negative_raises_value_error():
+    left, right = _mismatching_pair(1)
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(left, right, [((1,), {})], max_mismatches=-1)
+
+
+def test_to_json_includes_truncated_key():
+    left, right = _mismatching_pair(1)
+    result = BehaviorComparator().compare(left, right, [((1,), {})])
+
+    assert result.to_json()["truncated"] is False
+
+
+def test_to_json_includes_truncated_true_when_stopped_early():
+    left, right = _mismatching_pair(1)
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.to_json()["truncated"] is True

```

### R6
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 4c40fea..84c1163 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -26,6 +26,7 @@ class BehaviorComparisonResult:
     equivalent: bool
     cases: int
     mismatches: list[BehaviorMismatch]
+    truncated: bool = False
 
     def to_json(self) -> dict[str, Any]:
         """Serialize to a JSON-compatible dict."""
@@ -33,6 +34,7 @@ class BehaviorComparisonResult:
             "equivalent": self.equivalent,
             "cases": self.cases,
             "mismatches": [mismatch.__dict__ for mismatch in self.mismatches],
+            "truncated": self.truncated,
         }
 
 
@@ -44,16 +46,25 @@ class BehaviorComparator:
         original: Callable[..., Any],
         transformed: Callable[..., Any],
         cases: list[tuple[tuple[Any, ...], dict[str, Any]]],
+        *,
+        max_mismatches: int | None = None,
     ) -> BehaviorComparisonResult:
+        if max_mismatches is not None and max_mismatches < 1:
+            raise ValueError("max_mismatches must be >= 1")
         mismatches: list[BehaviorMismatch] = []
+        truncated = False
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
             mismatches.extend(_compare_observation(index, left, right))
+            if max_mismatches is not None and len(mismatches) >= max_mismatches:
+                truncated = index + 1 < len(cases)
+                break
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
             mismatches=mismatches,
+            truncated=truncated,
         )
 
 
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..574813a 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -1,5 +1,7 @@
 ﻿import sys
 
+import pytest
+
 from flatten.comparator import BehaviorComparator
 
 
@@ -33,3 +35,78 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_default_max_mismatches_is_untruncated():
+    def left():
+        raise ValueError("left")
+
+    def right():
+        raise ValueError("right")
+
+    result = BehaviorComparator().compare(left, right, [((), {})])
+
+    assert result.truncated is False
+    assert result.to_json()["truncated"] is False
+
+
+def test_behavior_comparator_stops_once_accumulated_mismatches_reach_max():
+    def left(n):
+        raise ValueError(f"left-{n}")
+
+    def right(n):
+        raise ValueError(f"right-{n}")
+
+    cases = [((0,), {}), ((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.cases == 3
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0
+    assert result.truncated is True
+
+
+def test_behavior_comparator_not_truncated_when_threshold_reached_on_last_case():
+    def left(n):
+        raise ValueError(f"left-{n}")
+
+    def right(n):
+        raise ValueError(f"right-{n}")
+
+    cases = [((0,), {}), ((1,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=2)
+
+    assert result.cases == 2
+    assert len(result.mismatches) == 2
+    assert result.truncated is False
+
+
+def test_behavior_comparator_keeps_all_mismatches_from_the_case_that_crosses_threshold():
+    def left(n):
+        print("a")
+        return 1
+
+    def right(n):
+        print("b")
+        return 2
+
+    cases = [((0,), {}), ((1,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases, max_mismatches=1)
+
+    assert result.cases == 2
+    assert len(result.mismatches) == 2
+    assert {m.field for m in result.mismatches} == {"return", "effects"}
+    assert all(m.case_index == 0 for m in result.mismatches)
+    assert result.truncated is True
+
+
+@pytest.mark.parametrize("bad_value", [0, -1])
+def test_behavior_comparator_rejects_non_positive_max_mismatches(bad_value):
+    def noop():
+        return None
+
+    with pytest.raises(ValueError):
+        BehaviorComparator().compare(noop, noop, [((), {})], max_mismatches=bad_value)

```

## 요청

각 변경(R1~R6)을 **독립적으로** 적대적으로 리뷰해라. 다른 변경과 비교해 점수를 상대평가하지 말고, 각각을 스펙(과제 원문) 대비 절대 기준으로 본다.

각 변경마다 다음을 JSON 으로 내라 (전체를 하나의 JSON 객체, 키는 R1..R6):
- `defects`: 결함 목록. 항목마다 `severity`("high"|"medium"|"low"), `kind`("correctness"|"spec_mismatch"|"edge_case"|"behavior_change"|"test_weakness"|"unneeded_change"|"other"), `description`(한두 문장, diff 의 어느 부분인지 명시)
- `spec_met`: true/false — 과제 원문의 요구를 빠짐없이 충족하는가
- `scores`: `correctness`, `minimality`(불필요한 변경 없이 최소인가), `test_quality`, 각 1~5 정수
- `verdict`: 한 문장

결함이 없으면 `defects` 는 빈 배열로 둬라. 근거 없는 지적은 하지 마라. 출력은 JSON 하나만, 앞뒤 설명 없이.
