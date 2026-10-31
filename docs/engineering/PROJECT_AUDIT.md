# Project Audit

Date: 2026-06-13

## Package Structure

```text
flatten-polymorph
├── src/flatten/                 # implementation package and CLI module
├── src/flatten_polymorph/       # compatibility import alias
├── tests/                       # regression, policy, harness, CLI, package tests
├── tests/differential/          # executable policy fixtures
├── tests/golden/                # safe and unsafe golden corpus
├── benchmarks/                  # OSS catalog plus executable safety benchmark suite
├── docs/                        # architecture, policy, safety, examples, reports
├── examples/                    # executable user-facing examples
├── scripts/                     # release gate automation
└── .github/workflows/           # CI jobs
```

## Public CLI/API

Public imports are exposed from `flatten.__init__`: `CallSite`,
`ClosureStatus`, `ClosureVerdict`, `OracleRecord`, `RewriteDecision`,
`TransformPlan`, `ClosureChecker`, `ClosureConfig`, `RewritePlanner`,
`assert_equivalent`, `collapse_source`, `flatten_callsite`, and
`hash_return`. The compatibility package `flatten_polymorph` forwards to
`flatten`.

The public CLI is `flatten` / `python -m flatten` with subcommands:
`analyze`, `trace`, `plan`, `rewrite`, `verify`, `report`, `evaluate`, and
`benchmark`. This pass adds the separate reproducible evidence command
`python -m benchmarks.runner` and the optional console script
`flatten-benchmark`.

## Current Architecture

```text
source files
  │
  ├─ static.py / discovery.py
  │    └─ class graph, call-site ids, risk flags
  │
  ├─ tracer.py / observations.py
  │    └─ runtime observations bound to exact call sites
  │
  └─ closure.py
       └─ ClosureVerdict: CLOSED, PROBABLY_CLOSED, OPEN, UNSAFE, UNKNOWN
            │
            ▼
       contracts.RewriteDecision.from_verdict
            │  only CLOSED + positive evidence + no blockers is allowed
            ▼
       planner.py
            └─ TransformPlan emission and LibCST replacement
                  │
                  ▼
       transformer.py / collapse.py / dispatch.py
                  │
                  ▼
       harness.py / comparator.py / evaluation.py
            └─ observed-input behavior evidence, reports, metrics
```

## Core Module Responsibilities

- `contracts.py`: frozen data contracts and rewrite authorization policy.
- `closure.py`: conservative closure/risk classification over observed
  receiver implementations.
- `static.py`: AST class graph extraction and static risk flags.
- `discovery.py`: LibCST call-site discovery with stable source positions.
- `observations.py`: structured observation schema parsing and type identity.
- `planner.py`: opt-in planning; refuses non-safe `RewriteDecision` values.
- `transformer.py`, `collapse.py`, `dispatch.py`: LibCST rewrites.
- `harness.py`: function and subprocess module equivalence checks.
- `evaluation.py`, `comparator.py`, `proofs.py`, `report.py`: evidence and
  reporting helpers.
- `cli.py`: command-line orchestration.
- `benchmarks/runner.py`: executable safety benchmark and evidence output.
- `tools/check_evidence.py`: CI evidence gate over benchmark JSON.

## Current Safety Assumptions

- Observation is evidence, not proof.
- A rewrite requires `ClosureStatus.CLOSED`, non-empty positive evidence, and
  no blockers.
- `PROBABLY_CLOSED`, `OPEN`, `UNSAFE`, and `UNKNOWN` do not authorize rewrites.
- Rewrites are opt-in and `rewrite --apply --entry` requires explicit cases
  unless `--skip-verify` is passed.
- Harness equivalence covers only replayed inputs; it is not whole-program
  semantic proof.
- Guarded dispatch keeps a fallback dynamic call for unmatched receiver types.

## Current Unsupported Or Risk Cases

- Dynamic imports and import hooks.
- Plugin loading and dependency injection containers.
- Runtime subclass creation.
- Monkey patching, `setattr`, and method reassignment.
- `__getattr__`, `__getattribute__`, custom `__setattr__`, and
  `__delattr__`.
- Descriptors, properties, classmethod/staticmethod binding edge cases.
- Custom metaclasses and `__init_subclass__` hooks.
- ABC virtual subclasses and Protocol structural typing.
- Multiple inheritance, diamond inheritance, `super()`, and MRO-sensitive
  dispatch.
- Module reload, runtime code generation, C extensions, native behavior,
  async/generator methods, and reflection-heavy code.

## Current Defects, TODO, Incomplete Code, Dead Code

- `closure._is_final()` contains a documented limitation and a `pass` branch
  for runtime detection of `typing.final` on classes. Current tests rely on
  explicit `__final__`/policy evidence and static reporting, not runtime
  type-checker semantics.
- The older OSS catalog benchmark in `src/flatten/benchmarks.py` remains
  catalog-only and reports zero evaluated projects; this is documented as a
  release blocker for repository-scale empirical claims.
- Native Windows mutation testing remains unsupported by `mutmut`; that is an
  external validation limitation rather than in-tree dead code.

## Files Touched In This Pass

- `benchmarks/__init__.py`
- `benchmarks/cases/policy_cases.json`
- `benchmarks/baseline.json`
- `benchmarks/metrics.py`
- `benchmarks/report.py`
- `benchmarks/runner.py`
- `benchmarks/README.md`
- `tools/check_evidence.py`
- `tests/test_benchmark_suite.py`
- `docs/engineering/PROJECT_AUDIT.md`
- `docs/SOUNDNESS.md`
- `.github/workflows/ci.yml`
- `pyproject.toml`
- `README.md`
- `AI/context/project_summary.md`
- `AI/context/architecture.md`
- `AI/decisions/decision_log.md`
- `AI/tasks/current_tasks.md`

## Files Intentionally Not Touched

- `src/flatten/contracts.py`, `closure.py`, `planner.py`, `harness.py`, and
  rewrite modules: the existing conservative policy already satisfied the
  evidence gate requirements, so this pass did not widen rewrite authority.
- User-dirty files `src/flatten/comparator.py`, `src/flatten/evaluation.py`,
  and `tests/test_evidence_cli.py`.
- Existing differential and golden fixtures: this pass adds a separate
  benchmark suite instead of rewriting established regression fixtures.
- Historical lowercase `docs/soundness.md` path: replaced by the requested
  evaluator-facing `docs/SOUNDNESS.md` path on this case-insensitive Windows
  filesystem.
