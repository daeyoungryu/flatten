# flatten Architecture

Last updated: 2026-06-10

## Module Flow

```text
runtime calls
  -> tracer.py       records OracleRecord values
  -> closure.py      checks whether observed impls are closed
  -> dispatch.py     builds replacement expressions
  -> collapse.py     applies TransformPlan replacements with LibCST
  -> harness.py      compares original and transformed behavior
```

## Contracts

All shared records live in `src/flatten/contracts.py` to avoid circular imports:

- `OracleRecord`
- `ClosureVerdict`
- `TransformPlan`

## Dependency Boundaries

- `contracts.py` depends only on stdlib dataclasses/typing and LibCST types.
- `tracer.py`, `closure.py`, `collapse.py`, `dispatch.py`, and `harness.py` are
  independently importable.
- All code transformation is done with LibCST. `ast.unparse` is not used.

## Test Coverage

- Unit tests cover tracer, closure, collapse, dispatch, and harness.
- `tests/test_integration.py` covers A1-A6 and the end-to-end flow.
