# flatten

Flatten explores Python polymorphic dispatch with runtime tracing and LibCST
rewrites. It records observed implementations, checks whether the observed
hierarchy is closed, builds direct or `isinstance` dispatch expressions, applies
planned CST replacements, and verifies behavior equivalence.

## Install

```powershell
cd C:\Users\Com\Documents\Claude\Projects\flatten
python -m pip install -e ".[dev]"
```

## Quick Example

```python
from flatten import ClosureChecker, Tracer, assert_equivalent, trace_calls

with trace_calls(Base.process) as tracer:
    for obj in objects:
        obj.process(42)

impls = sorted({record.impl_class for record in tracer.records}, key=lambda cls: cls.__name__)
verdict = ClosureChecker().check("Base.process", impls)

assert_equivalent(original_func, flattened_func, [((42,), {})])
```

## Test

```powershell
python -m pytest tests/ -x -v
```

## Implemented Modules

- `contracts.py`: frozen `OracleRecord`, `ClosureVerdict`, and `TransformPlan`.
- `tracer.py`: Python 3.12+ `sys.monitoring` setup with shared record creation
  through runtime tracing, plus `sys.settrace` fallback for Python 3.8-3.11.
- `closure.py`: OS1-OS5 open-signal checks and recursive subclass discovery.
- `collapse.py`: LibCST batch replacement using `TransformPlan`.
- `dispatch.py`: direct-call and `isinstance` chain LibCST builders.
- `harness.py`: behavior hashing and detailed equivalence assertions.
