# Soundness Audit

This document states the current soundness model for `flatten-polymorph`.
The project treats observation as evidence, not proof. A rewrite is allowed
only when the pipeline has positive closure evidence, no known dynamic-dispatch
blockers, a SAFE proof classification, and behavior verification for explicit
cases when `rewrite --apply --entry` is used.

## Soundness Philosophy

The tool is conservative by design:

- Missing evidence is not evidence of safety.
- Runtime observation alone never closes an open world.
- `PROBABLY_CLOSED`, `OPEN`, `UNSAFE`, and `UNKNOWN` verdicts do not rewrite.
- A `CLOSED` verdict is only actionable when it also carries non-empty evidence,
  no blockers, and a SAFE proof classification.
- Validation checks observed cases only. It is a regression gate, not a proof of
  all future executions.
- Plan files are untrusted inputs. They must match the source hash and carry
  the call-site and verdict fields emitted by the planner.

## Pipeline Audit

### 1. Observation

Implementation:

- `flatten.tracer.Tracer`
- `flatten.observations.ObservationRecord`, `TypeRef`, `FunctionRef`
- CLI: `flatten trace`

Input:

- A Python source file.
- An entry point in `module:function` form.
- Runtime execution of that entry point.

Output:

- A JSON list of observations.
- Each bound observation records a `call_site_id`, receiver type, resolved
  function, method name, frame/module evidence, and ordering metadata.

Failure conditions:

- Entry point cannot be imported or found.
- Execution raises before producing usable observations.
- Runtime frame evidence cannot be bound to a static call site.
- Observed receiver type cannot later be restored from the source/module.

Conservative refusal conditions:

- Unbound observations are excluded from rewrite planning.
- Type restoration failure yields `UNKNOWN`.
- Observations are grouped by method qualname before closure analysis; evidence
  from one method cannot authorize rewriting another method.

Soundness assumptions:

- The traced execution is representative only for the concrete inputs that ran.
- Python frame/bytecode position metadata identifies the call site accurately
  for normal synchronous execution.
- Observation identity is stable enough to restore local classes by module,
  qualname, and source path during planning.

### 2. Closure Analysis

Implementation:

- `flatten.closure.ClosureChecker`
- `flatten.static.analyze_class_hierarchy`
- CLI helper: `_verdicts_from_observations`

Input:

- Bound observations grouped by method qualname.
- Restored receiver classes.
- Optional static class hierarchy extracted from the source file.
- Closure configuration such as `closed_world`, sealed roots, and final support.

Output:

- One `ClosureVerdict` per observed method group.
- Status is one of `CLOSED`, `PROBABLY_CLOSED`, `OPEN`, `UNSAFE`, or `UNKNOWN`.
- Verdicts carry known implementations, blockers/open signals, reasons, and
  evidence strings.

Failure conditions:

- No observations for a method.
- Type restoration failure.
- Static parse failure.
- Missing or incomplete static class graph for the declared method owner.

Conservative refusal conditions:

- Unobserved subclasses produce `OPEN`.
- Complete local hierarchy without positive closure evidence produces
  `PROBABLY_CLOSED`, not `CLOSED`.
- Dynamic dispatch hazards produce `UNSAFE`.
- Custom attribute hooks, custom metaclasses, descriptor/property dispatch,
  multiple inheritance, dynamic imports, and dynamic code execution block
  rewrites.
- Source-level class attribute assignment is treated as possible monkey patching.
- Source-level `setattr` is treated as possible monkey patching.

Soundness assumptions:

- `typing.final`, final methods, explicit sealed roots, or explicit closed-world
  configuration are the only positive closure signals currently accepted.
- The static class graph covers the source file being rewritten, not arbitrary
  future modules.
- Runtime `__subclasses__` evidence is weaker than static source evidence and
  does not imply future-world closure.

### 3. Rewrite Decision

Implementation:

- `flatten.contracts.RewriteDecision`
- `flatten.proofs.ProofArtifact`
- `flatten.proofs.classify_rewrite_decision`
- `flatten.planner.RewritePlanner.decide`

Input:

- `ClosureVerdict` values from closure analysis.

Output:

- Structured rewrite authorization records.
- Each decision records allow/refuse state, status, confidence, reasons,
  blockers, evidence, reason code, proof status, and proof evidence.
- Each emitted rewrite plan carries a `proof_artifact` with callsite, observed
  targets, closure status, passed/failed closure rules, risk level, and
  rewrite authorization.

Failure conditions:

- Missing evidence on a `CLOSED` verdict.
- Unknown or unsupported closure status.
- Blockers on an otherwise closed-looking verdict.

Conservative refusal conditions:

- `allowed` is false unless status is `CLOSED`, blockers are empty, and evidence
  is non-empty.
- Proof status must be `safe`; `unsafe` and `unknown` decisions cannot feed
  rewrite planning.

Soundness assumptions:

- `RewriteDecision` is the single authorization boundary between analysis and
  transformation.
- The proof classifier is intentionally coarse: it can refuse safe cases, but it
  must not mark unsupported cases as SAFE.

### 4. CST Transform

Implementation:

- `flatten.discovery.discover_call_sites`
- `flatten.planner.RewritePlanner.plan_from_observations`
- `flatten.transformer.rewrite_source_with_plan`
- `flatten.collapse.collapse_source` for legacy target-node transforms

Input:

- Source text.
- Static call sites.
- Bound observations.
- SAFE decisions and their matching verdicts.

Output:

- `TransformPlan` objects for exact call-site ranges.
- Rewritten source generated by LibCST.
- Direct call rewrites for a single observed receiver type.
- Guarded `isinstance` expression rewrites for multiple receiver types.

Failure conditions:

- Call site has no bound observations.
- No SAFE verdict matches the call site's observed method.
- Receiver type cannot be ordered against the verdict's known implementations.
- Target range is missing or no longer matches the LibCST position metadata.

Conservative refusal conditions:

- A SAFE verdict for one method cannot rewrite another method's call site.
- The transformer rewrites only exact source ranges.
- Non-name guarded receivers are evaluated once through a temporary in supported
  return-statement contexts.
- Plans with non-closed verdicts are ignored by the position transformer.

Soundness assumptions:

- LibCST position metadata remains aligned with the source used to produce the
  plan.
- Replacing a method call with `Class.method(receiver, *args)` preserves Python
  binding semantics only for ordinary function methods that passed descriptor
  and dynamic lookup checks.
- Guarded rewrites preserve fallback dynamic dispatch for unmatched receiver
  types.

### 5. Validation

Implementation:

- `flatten.harness.assert_equivalent`
- `flatten.harness.assert_modules_equivalent_subprocess`
- CLI: `flatten verify`, `flatten rewrite --apply --entry --cases`

Input:

- Original and rewritten entry functions/modules.
- Explicit cases from `--cases`.
- Optional side-effect collectors in the Python API.

Output:

- Pass/fail equivalence result.
- Compared dimensions include return value, exception type, exception message,
  stdout, stderr, and collected effects.

Failure conditions:

- Outcome differs (`return` vs `raise`).
- Return value differs.
- Exception type or message differs.
- Captured stdout/stderr/effects differ.
- Case file has invalid shape.

Conservative refusal conditions:

- `rewrite --apply` requires `--entry` unless `--skip-verify` is explicit.
- `rewrite --apply --entry` requires `--cases`; the old implicit single empty
  case is not accepted as a gate.
- Validation failure aborts the rewrite command.

Soundness assumptions:

- Validation only proves equivalence for the supplied cases.
- Side effects are only checked when observable through stdout/stderr or
  explicit effect collectors.
- Subprocess validation improves isolation but still depends on deterministic
  entry behavior for the supplied cases.

## Dynamic Feature Classification

The labels below classify features with respect to rewrite permission, not
whether Python code using the feature is valid.

### Classification Criteria

SAFE:

- The feature is supported by the current pipeline and has positive evidence
  that it preserves dispatch semantics for the rewritten call site.
- No blocker is present.
- The final `RewriteDecision` is allowed and proof status is `safe`.

UNSAFE:

- The feature can change method lookup, binding, class membership, dispatch
  targets, or side effects in a way the current model cannot preserve.
- The checker has an explicit blocker or risk signal for it.

UNKNOWN:

- The feature may be safe in some programs, but the current implementation does
  not collect enough evidence to prove it.
- UNKNOWN must refuse rewrite.

### Feature Matrix

| Feature | Current Classification | Basis | Rewrite Policy |
| --- | --- | --- | --- |
| Monkey patch | UNSAFE | Static class-attribute assignment and runtime method replacement risks can change dispatch after observation. | Reject. |
| `setattr` | UNSAFE | Static analysis flags source-level `setattr`; custom `__setattr__` is an UNSAFE closure blocker. | Reject unless future analysis proves irrelevant to the target hierarchy. |
| Descriptor | UNSAFE | Non-function descriptors and properties can alter binding and lookup semantics. | Reject. |
| Metaclass | UNSAFE | Custom metaclasses can alter construction, lookup, class attributes, and subclass behavior. | Reject. |
| Dynamic import | UNSAFE | Imports inside observed methods can trigger import-time side effects that change dispatch state. | Reject. |
| `importlib.reload` | UNKNOWN | The current static scanner detects imports, not all reload-driven module mutation patterns. Reload can replace classes/functions after observation. | Reject unless detected as dynamic import/code mutation by surrounding evidence; otherwise treat as unsupported. |
| Plugin registration | UNKNOWN | Registration can introduce dispatch targets after observation, often through decorators, registries, or entry points outside the local class graph. | Reject when hooks such as `__init_subclass__` or dynamic registry patterns are detected; do not claim closed-world safety without an explicit sealed boundary. |
| `exec` | UNSAFE | Dynamic code execution can create or replace classes/functions and mutate dispatch targets. | Reject. |
| `eval` | UNSAFE | Dynamic evaluation can execute code or access dynamically generated dispatch behavior. | Reject. |
| Runtime code generation | UNKNOWN/UNSAFE | Explicit `eval`, `exec`, or `__import__` is UNSAFE; other generation mechanisms may be invisible to the current scanner. | Reject when detected; otherwise do not use observation alone as proof. |

## Known Soundness Boundaries

- Future imports can add subclasses that were not in the source graph.
- External packages are not closed unless explicitly modeled as sealed.
- Reflection-heavy code may hide dispatch mutation from static analysis.
- Case-based validation does not cover untested branches.
- Plan-file provenance is syntactic and source-hash based; it is not a
  cryptographic proof that the plan was produced by a trusted planner.

## Required Invariants

1. Every emitted rewrite must trace back to a bound call site.
2. Every bound call site must use the verdict for its own observed method.
3. Every rewrite must have a `CLOSED` verdict with evidence and no blockers.
4. Every rewrite decision must have SAFE proof status.
5. Every emitted rewrite plan must carry a `proof_artifact`.
6. `rewrite --apply --entry` must use explicit validation cases.
7. Any disagreement between analysis, proof, transform, or validation must
   refuse the rewrite.
