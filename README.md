# flatten

런타임 추적(sys.monitoring) + CST 변환(LibCST)으로 Python 다형 호출을 단일 실행 경로로 펼친다.

## 빠른 시작

```python
from flatten import Tracer, ClosureChecker, assert_equivalent

# 1. 런타임 추적
tracer = Tracer()
with tracer:
    obj.process(42)

# 2. 닫힌/열린 계층 판정
checker = ClosureChecker()
verdict = checker.check("MyBase.process", [ImplA, ImplB])
print(verdict.is_closed, verdict.open_signals)

# 3. 동등성 검증
assert_equivalent(original_func, flattened_func, [((42,), {})])
```

## 설치

```bash
pip install -e ".[dev]"
```

Python 3.12+ 필수 (`sys.monitoring` API 사용).
