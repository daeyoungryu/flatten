# 코드 리뷰 요청 (읽기 전용)

아래는 같은 과제를 서로 독립적으로 수행한 6개의 변경(diff)이다. 저장소에 접근하거나 git 명령을 실행하지 말고, 이 문서에 들어 있는 내용만 근거로 판단해라. 결함 목록은 주지 않는다 — 무엇을 볼지는 네가 정하라.

## 과제 원문

버그 리포트: `BehaviorComparator.compare` 로 여러 케이스를 비교하면 앞쪽 케이스에서 난 불일치가 결과에서 사라진다(뒤 케이스가 일치하면 `equivalent` 가 True 로 나오기도 한다). 원인을 찾아 최소한으로 수정하고, 회귀 테스트를 tests/ 아래에 추가한 뒤 저장소 루트에서 `python -m pytest tests -q` 전체를 실행해 결과를 요약해라. 질문하지 말고 끝까지 진행해. 커밋은 하지 마.

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
            mismatches = _compare_observation(index, left, right)
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
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..c6d74b6 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -33,3 +33,20 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_keeps_mismatch_from_earlier_case():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 1 else value
+
+    result = BehaviorComparator().compare(
+        left, right, [((1,), {}), ((2,), {})]
+    )
+
+    assert result.equivalent is False
+    assert result.cases == 2
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0

```

### R2
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..7ba1957 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -20,6 +20,23 @@ def test_behavior_comparator_reports_equivalent_return_and_streams():
     assert result.mismatches == []
 
 
+def test_behavior_comparator_keeps_mismatches_from_earlier_cases():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 1 else value
+
+    result = BehaviorComparator().compare(
+        left, right, [((1,), {}), ((2,), {})]
+    )
+
+    assert result.equivalent is False
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0
+    assert result.mismatches[0].field == "return"
+
+
 def test_behavior_comparator_reports_exception_message_mismatch():
     def left():
         raise ValueError("left")

```

### R3
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..70a042c 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -33,3 +33,18 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_keeps_mismatch_from_earlier_case():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 0 else value
+
+    result = BehaviorComparator().compare(left, right, [((0,), {}), ((1,), {})])
+
+    assert result.equivalent is False
+    assert result.cases == 2
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0

```

### R4
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..6d3d910 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -33,3 +33,34 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_keeps_earlier_mismatch_when_later_case_matches():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 1 else value
+
+    cases = [((1,), {}), ((2,), {})]
+
+    result = BehaviorComparator().compare(left, right, cases)
+
+    assert result.equivalent is False
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0
+
+
+def test_behavior_comparator_accumulates_mismatches_across_all_cases():
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
+    assert result.equivalent is False
+    assert [m.case_index for m in result.mismatches] == [0, 1, 2]

```

### R5
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..95920bd 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -33,3 +33,19 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_keeps_mismatch_from_earlier_case():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 1 else value
+
+    result = BehaviorComparator().compare(
+        left, right, [((1,), {}), ((2,), {})]
+    )
+
+    assert result.equivalent is False
+    assert result.cases == 2
+    assert [m.case_index for m in result.mismatches] == [0]

```

### R6
```diff
diff --git a/src/flatten/comparator.py b/src/flatten/comparator.py
index 87d5eaa..4c40fea 100644
--- a/src/flatten/comparator.py
+++ b/src/flatten/comparator.py
@@ -49,7 +49,7 @@ class BehaviorComparator:
         for index, (args, kwargs) in enumerate(cases):
             left = capture_behavior(original, *args, **kwargs)
             right = capture_behavior(transformed, *args, **kwargs)
-            mismatches = _compare_observation(index, left, right)
+            mismatches.extend(_compare_observation(index, left, right))
         return BehaviorComparisonResult(
             equivalent=not mismatches,
             cases=len(cases),
diff --git a/tests/test_comparator.py b/tests/test_comparator.py
index 2517928..46c2f20 100644
--- a/tests/test_comparator.py
+++ b/tests/test_comparator.py
@@ -33,3 +33,18 @@ def test_behavior_comparator_reports_exception_message_mismatch():
     assert result.mismatches[0].field == "exception"
     assert "left" in result.mismatches[0].original
     assert "right" in result.mismatches[0].transformed
+
+
+def test_behavior_comparator_keeps_earlier_case_mismatch_when_later_case_matches():
+    def left(value):
+        return value
+
+    def right(value):
+        return value + 1 if value == 0 else value
+
+    result = BehaviorComparator().compare(left, right, [((0,), {}), ((1,), {})])
+
+    assert result.equivalent is False
+    assert len(result.mismatches) == 1
+    assert result.mismatches[0].case_index == 0
+    assert result.mismatches[0].field == "return"

```

## 요청

각 변경(R1~R6)을 **독립적으로** 적대적으로 리뷰해라. 다른 변경과 비교해 점수를 상대평가하지 말고, 각각을 스펙(과제 원문) 대비 절대 기준으로 본다.

각 변경마다 다음을 JSON 으로 내라 (전체를 하나의 JSON 객체, 키는 R1..R6):
- `defects`: 결함 목록. 항목마다 `severity`("high"|"medium"|"low"), `kind`("correctness"|"spec_mismatch"|"edge_case"|"behavior_change"|"test_weakness"|"unneeded_change"|"other"), `description`(한두 문장, diff 의 어느 부분인지 명시)
- `spec_met`: true/false — 과제 원문의 요구를 빠짐없이 충족하는가
- `scores`: `correctness`, `minimality`(불필요한 변경 없이 최소인가), `test_quality`, 각 1~5 정수
- `verdict`: 한 문장

결함이 없으면 `defects` 는 빈 배열로 둬라. 근거 없는 지적은 하지 마라. 출력은 JSON 하나만, 앞뒤 설명 없이.
