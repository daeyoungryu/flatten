# flatten Project Summary

Last updated: 2026-06-10

## Overview

`flatten` is a Python package for flattening observed polymorphic dispatch into
single-path LibCST expressions. The package combines runtime tracing, closure
analysis, CST transformation planning, dispatch expression generation, and
behavior equivalence checks.

## Current Status

Implemented:

- Data contracts are frozen in `src/flatten/contracts.py`.
- Runtime tracing records `OracleRecord` values with qualname, implementation
  class, positional args, keyword-only args, and return value.
- Python version split uses `sys.version_info >= (3, 12)`.
- Closure analysis exposes OS1-OS5 signals and recursive subclass discovery.
- Collapse transformation applies `TransformPlan` batches with LibCST.
- Dispatch generation supports direct calls and multiple-implementation
  `isinstance` expressions.
- Harness computes behavior hashes and reports detailed divergence.
- Tests cover A1-A6 including an end-to-end polymorphic pipeline.
- Hardening now includes opt-in rewrites, JSON/HTML reports, CLI, confidence
  score, Hypothesis properties, ruff, mypy strict, and 90% coverage.

## Verification

Use:

```powershell
python -m pytest tests/ -x -v
python -m pytest --cov=flatten --cov-fail-under=90
python -m ruff check src tests
python -m mypy src
```
