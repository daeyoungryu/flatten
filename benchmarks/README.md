# Benchmark Suite

This directory contains the local safety benchmark suite for `flatten-polymorph`.
It is separate from the older OSS project catalog in `projects.csv`: the catalog
tracks future repository-scale evaluation targets, while this suite is
executable in CI without network access.

Case files live in `benchmarks/cases/*.json`. JSON was chosen over YAML to avoid
adding a runtime dependency while keeping the corpus readable and stable under
GitHub Actions.

Run:

```powershell
python -m benchmarks.runner --format json --output benchmark-results.json
python -m benchmarks.runner --format markdown --output benchmark-report.md
python tools/check_evidence.py benchmark-results.json
```

The runner derives rewrite decisions from the real
`flatten.contracts.RewriteDecision.from_verdict` policy and runs equivalence
probes through `flatten.harness.assert_modules_equivalent_subprocess`.

