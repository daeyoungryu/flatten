# flatten Architecture

## Data Flow

`flatten` processes source through discovery, runtime observation, static
hierarchy extraction, closure checking, proof classification, planning, LibCST
rewrite, differential validation, and reporting.

The pipeline is intentionally conservative:

```text
source
-> discover call sites
-> collect runtime observations
-> extract static hierarchy and dynamic risk signals
-> produce closure verdicts
-> classify rewrite proof
-> emit rewrite decisions and plans
-> apply exact CST rewrite
-> compare behavior
-> report evidence
```

## Module Responsibilities

- `flatten.discovery`: source-positioned method call-site discovery.
- `flatten.tracer`: runtime receiver and caller evidence collection.
- `flatten.observations`: stable JSON observation contracts.
- `flatten.static`: class hierarchy and dynamic risk extraction.
- `flatten.closure`: CLOSED, PROBABLY_CLOSED, OPEN, UNSAFE, UNKNOWN verdicts.
- `flatten.proofs`: SAFE, UNSAFE, UNKNOWN rewrite proof classification.
- `flatten.planner`: rewrite authorization and transform plan creation.
- `flatten.transformer`: exact position-based LibCST replacement.
- `flatten.comparator`: behavior comparison of original and rewritten callables.
- `flatten.evaluation`: reproducible counts and precision/recall metrics.
- `flatten.report`: human and HTML report rendering.
- `flatten.cli`: command-line orchestration.

## Public API

The stable public dataclasses are `CallSite`, `ObservationRecord`,
`ClosureVerdict`, `RewriteDecision`, `TransformPlan`, `EvaluationCounts`,
`EvaluationMetrics`, `ProofEvidence`, and `BehaviorComparisonResult`.

Public API consumers should treat runtime observations as evidence for observed
executions only. They should not use observation count alone as rewrite proof.

## Evidence Platform

The evidence platform records total call sites, candidate call sites, rewritten
call sites, rejected call sites, unsafe call sites, unknown call sites,
precision, recall, false positive rate, and false negative rate. Metrics with
no labeled corpus are reported as `null`, not guessed.

## Safety Limits

Runtime observation is evidence for observed executions only. A rewrite requires
positive closure evidence and SAFE proof classification. UNKNOWN never rewrites.
UNSAFE never rewrites.

Behavior comparison validates replayed cases, return values, stdout, stderr,
exception type, exception message, and optional effects. Passing comparison is
runtime evidence, not a proof for unobserved inputs.

## False Positives

False positives can occur if a labeled corpus marks an unsafe call site as
rewritten, if dynamic behavior is hidden outside observed executions, or if a
plan file is trusted without matching source and evidence checks.

## False Negatives

False negatives are expected under conservative policy. Final classes with
unsupported descriptors, dynamic imports, custom metaclasses, or incomplete
hierarchy evidence can be rejected even when a human can prove safety.

## Unsupported Python Features

Unsupported or rejected features include dynamic `__getattr__`, custom
`__getattribute__`, monkey patching, custom metaclasses, descriptor/property
dispatch, complex multiple inheritance, dynamic imports, eval/exec, async
methods, generator methods, and open-world plugin extension points.
