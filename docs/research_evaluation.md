# Research Evaluation

This document is the research-grade evaluation contract for `flatten-polymorph`.
It separates implemented local gates from external OSS evaluation that requires
checking out and running third-party projects.

## Current Quantitative Status

| KPI | Current Value |
| --- | --- |
| Project Catalog Size | 35 |
| Projects Evaluated | 0 |
| Total Call Sites | 0 |
| Candidates | 0 |
| Rewritten | 0 |
| Rejected | 0 |
| Unsafe | 0 |
| Unknown | 0 |
| False Positives | 0 |
| Behavior Mismatches | 0 |
| Rewrite Success Rate | n/a |
| Proof Coverage | n/a |
| Closure Coverage | n/a |

Status: the OSS suite is cataloged and CI-gated for schema sanity. It is not yet
a completed empirical evaluation over checked-out OSS source trees.

## Threats to Validity

- Catalog sanity is not equivalent to evaluating live project source.
- Dynamic import paths, optional dependencies, and plugin systems may hide
  dispatch behavior from local static analysis.
- Differential tests only cover supplied cases.
- Projects with generated code or C-extension-backed behavior may undercount
  relevant Python call sites.
- Benchmark results can change as upstream projects evolve.

## Known Unsound Cases

The tool must reject, or classify as unknown, cases involving:

- monkey patching;
- `setattr` or class attribute mutation;
- non-function descriptors and properties;
- custom metaclasses;
- dynamic imports and reload-like module replacement;
- plugin registration that adds future dispatch targets;
- `eval`, `exec`, `__import__`, or other runtime code generation;
- incomplete open-world subclass graphs.

## False Positive Analysis

A false positive is a rewritten call site that should have been rejected. The
release target is `False Positives = 0`. Current local gates include P0
regression tests, mutation harness tests, differential policy fixtures, and
proof-artifact presence checks. The OSS benchmark stage must report false
positives separately from behavior mismatches.

## False Negative Analysis

A false negative is a rejected call site that could have been safely rewritten.
False negatives are acceptable for soundness but should be measured so the tool
does not become uselessly conservative. Current local metrics expose rejected,
unsafe, unknown, and candidate counts; future OSS runs should label safe
opportunities where practical.

## Benchmark Methodology

1. Use `benchmarks/projects.csv` as the benchmark catalog.
2. Check out each project at a pinned commit before evaluation.
3. Run call-site discovery over Python source files.
4. Trace only deterministic, documented entry cases.
5. Generate plans and proof artifacts.
6. Run differential validation for every proposed rewrite.
7. Run mutation checks for every accepted rewrite family.
8. Emit JSON and Markdown summary reports.

## Reproducibility Guide

Run the local benchmark sanity gate:

```powershell
python -m flatten benchmark --catalog benchmarks/projects.csv --out-json benchmarks/summary.json --out-md benchmarks/summary.md
```

Run the local quality gate:

```powershell
python -m pytest -q
python -m ruff check .
```

For release builds, run:

```powershell
.\scripts\release_gate.ps1
```

## Artifact Evaluation Guide

Evaluation artifacts should include:

- benchmark catalog CSV;
- pinned project commit list;
- per-project JSON metrics;
- aggregate JSON and Markdown reports;
- proof artifacts for every rewrite plan;
- differential test logs;
- mutation test logs;
- CI run URL or local release-gate log.

## Release Gate

Do not release 0.2.0 unless all of the following are true:

- False Positives = 0;
- Behavior Mismatches = 0;
- at least 30 OSS projects evaluated from pinned source;
- ProofArtifact generation rate = 100%;
- differential test pass rate = 100%;
- mutation tests pass;
- CI is green;
- README publishes quantitative data.
