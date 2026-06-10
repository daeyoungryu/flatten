# flatten-polymorph

`flatten-polymorph` analyzes observed Python polymorphic dispatch with runtime
tracing and LibCST. It does not claim that finite runtime observation proves a
hierarchy is closed. Source rewrites are disabled by default and must be opted
into explicitly; generated rewrites include a warning that unobserved
implementations may exist.

## Install

```powershell
cd C:\Users\Com\Documents\Claude\Projects\flatten
python -m pip install -e ".[dev]"
```

The distribution name is `flatten-polymorph`; the import package remains
`flatten`.

## Quick Example

```python
from flatten import ClosureChecker, RewritePlanner, assert_equivalent, trace_calls

with trace_calls(Base.process) as tracer:
    for obj in objects:
        obj.process(42)

impls = sorted({record.impl_class for record in tracer.records}, key=lambda cls: cls.__name__)
verdict = ClosureChecker().check("Base.process", impls)
planner = RewritePlanner(opt_in=False)

assert_equivalent(original_func, flattened_func, [((42,), {})])
```

## Test

```powershell
python -m pytest tests/ -x -v
python -m pytest --cov=flatten --cov-fail-under=90
python -m ruff check src tests
python -m mypy src
```

## Implemented Modules

- `contracts.py`: frozen `OracleRecord`, `ClosureVerdict`, and `TransformPlan`.
- `tracer.py`: Python 3.12+ `sys.monitoring` or Python 3.10-3.11 `sys.settrace`.
- `closure.py`: OS1-OS5 open-signal checks and documented runtime-observation limits.
- `collapse.py`: LibCST batch replacement using `TransformPlan`.
- `dispatch.py`: direct-call and `isinstance` chain LibCST builders.
- `harness.py`: behavior hashing and detailed equivalence assertions.
- `planner.py`: opt-in rewrite planner.
- `report.py`: JSON and HTML analysis reports.
- `cli.py`: `flatten analyze` command.

## License

MIT. See `LICENSE`.
