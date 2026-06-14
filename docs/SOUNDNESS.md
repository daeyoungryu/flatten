# Soundness Report

`flatten-polymorph` is conservative by default. Runtime observation may provide
evidence, but it does not constitute proof. A rewrite is allowed only when
closure and behavioral evidence satisfy the configured safety policy.

## Definitions

- Observation: a runtime record that a call site resolved to a receiver type
  and implementation during one execution.
- Evidence: static or runtime facts that support a safety claim, such as final
  markers, closed-world package scans, or harness replay results.
- Proof: a complete argument that a rewrite preserves behavior for all relevant
  executions. This project does not claim full Python semantic proof.
- Closed hierarchy: a class hierarchy whose complete implementation set is
  known under the active policy.
- Probably closed: available evidence found no missing implementation, but no
  positive closure proof exists.
- Open world: code outside the scanned/declared boundary can add subclasses,
  monkey patches, plugins, imports, or native behavior.
- Safe rewrite: a rewrite authorized by `RewriteDecision.allowed=True`, derived
  from `ClosureStatus.CLOSED`, positive evidence, and no blockers.
- Behavior equivalence: matching return values, exceptions, stdout, stderr, and
  configured effects for replayed inputs.
- False positive: the tool rewrites when the benchmark expects reject or
  unsupported.
- False negative: the tool rejects or leaves unsupported when the benchmark
  expects rewrite.
- Unsupported case: a case outside the current modeled policy surface.

## Soundness Model

The system follows this model:

1. Bind observations to exact LibCST call-site positions.
2. Classify closure with `ClosureChecker`.
3. Convert the verdict to `RewriteDecision`.
4. Emit `TransformPlan` only for allowed decisions.
5. Verify behavior over explicit replay cases where rewrite is applied.

Observation narrows the candidate set; it does not prove no future or
unimported implementation exists. Harness verification is evidence over the
chosen inputs; it is not proof for unobserved receivers or inputs.

## Supported Safe Cases

The current policy can allow rewrite when there is positive closure evidence:

- `typing.final`/`__final__` class or method evidence.
- Explicit sealed root allowlist.
- Closed-world package scan with no missing static subclasses.
- Deterministic override sets with no dynamic dispatch blockers.
- Package-local class sets under a configured closed-world boundary.
- Guarded dispatch over a finite closed implementation set.

## Known Unsound Or Risky Cases

### Dynamic Imports

Risk: A later import can add subclasses or replace methods.
Why it matters: Observed executions may miss import-time side effects.
Current behavior: Classified as unsafe/open evidence and rejected.
Expected policy: Reject unless a closed import graph is proven.
Benchmark coverage: `late_import_subclass_001`, `import_hook_001`.

### Plugin Loading

Risk: Plugins register implementations outside the scanned graph.
Why it matters: Plugin systems are intentionally open world.
Current behavior: Rejected as unsafe/open.
Expected policy: Reject unless the plugin registry is frozen and enumerated.
Benchmark coverage: `plugin_registry_001`.

### Monkey Patching

Risk: Methods can be reassigned after observation.
Why it matters: Direct calls can bypass the patched method.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `monkey_patching_001`, `method_reassignment_001`,
`setattr_mutation_001`.

### Metaclass Mutation

Risk: Metaclasses can alter class creation, lookup, or registration.
Why it matters: Static class bodies do not capture metaclass effects.
Current behavior: Rejected.
Expected policy: Reject unless modeled explicitly.
Benchmark coverage: `metaclass_side_effect_001`.

### Dynamic Subclass Creation

Risk: `type()` or factory code can create implementations after analysis.
Why it matters: Closed sets become stale.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `dynamic_subclass_creation_001`.

### `__getattr__`

Risk: Missing attribute lookup can synthesize callables.
Why it matters: Flattening to a direct class method skips lookup semantics.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `getattr_001`.

### `__getattribute__`

Risk: Every attribute access can be intercepted.
Why it matters: Direct calls may bypass a different callable or side effect.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `getattribute_001`,
`non_equivalent_attribute_lookup_001`.

### Descriptors

Risk: `__get__` controls binding and returned callable identity.
Why it matters: `Class.method(obj, ...)` can differ from `obj.method(...)`.
Current behavior: Rejected.
Expected policy: Reject unless descriptor semantics are proven equivalent.
Benchmark coverage: `descriptor_001`, `non_equivalent_descriptor_001`.

### Properties

Risk: Property access runs arbitrary code.
Why it matters: Rewrite can change evaluation order or skip property code.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `property_001`.

### ABC Virtual Subclassing

Risk: `ABC.register()` creates virtual relationships invisible to nominal MRO.
Why it matters: Implementation sets are not closed by subclass traversal.
Current behavior: Rejected as unsupported/unsafe risk.
Expected policy: Reject unless virtual registrations are frozen.
Benchmark coverage: `abc_virtual_subclass_001`.

### Protocol Structural Typing

Risk: Any object with matching shape may satisfy the protocol.
Why it matters: The implementation set is structural, not nominal.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `protocol_structural_typing_001`.

### Multiple Inheritance / MRO

Risk: MRO order can select different methods under subclass combinations.
Why it matters: Guard order may not match Python resolution in all cases.
Current behavior: Rejected for unsafe MRO cases.
Expected policy: Reject unless a precise MRO proof exists.
Benchmark coverage: `multiple_inheritance_001`, `mro_sensitive_dispatch_001`,
`super_dependency_001`.

### Side-Effectful Attribute Access

Risk: Lookup can mutate state or produce observable effects.
Why it matters: Direct calls can skip lookup effects.
Current behavior: Rejected where detected; harness can expose mismatches.
Expected policy: Reject.
Benchmark coverage: `side_effectful_lookup_001`,
`non_equivalent_side_effect_001`.

### Module Reload

Risk: Reload can replace classes and method objects.
Why it matters: Previously closed evidence becomes stale.
Current behavior: Rejected.
Expected policy: Reject unless reload is excluded by policy.
Benchmark coverage: `module_reload_001`.

### Runtime Code Generation

Risk: `eval`/`exec`/import hooks can create behavior not present statically.
Why it matters: Static and observed evidence can be invalidated.
Current behavior: Rejected.
Expected policy: Reject.
Benchmark coverage: `runtime_code_generation_001`, `import_hook_001`.

### C Extensions / Native Behavior

Risk: Native code can implement dispatch semantics invisible to Python.
Why it matters: Python-level analysis cannot inspect native side effects.
Current behavior: Rejected as open/unknown.
Expected policy: Reject unless native behavior is modeled externally.
Benchmark coverage: `native_extension_dispatch_001`.

### Dependency Injection Containers

Risk: Containers substitute implementations dynamically.
Why it matters: Static class graphs do not enumerate runtime bindings.
Current behavior: Rejected as open world.
Expected policy: Reject unless bindings are frozen and audited.
Benchmark coverage: `dependency_injection_container_001`.

## Decision Table

| ClosureVerdict status | RewriteDecision policy |
| --- | --- |
| CLOSED | Allow candidate rewrite only with positive evidence and no blockers |
| PROBABLY_CLOSED | Unsupported; do not rewrite |
| OPEN | Reject |
| UNSAFE | Reject |
| UNKNOWN | Unsupported; do not rewrite |

This matches `RewriteDecision.from_verdict`: `allowed=True` only when status is
`CLOSED`, evidence is non-empty, and blockers are empty.

## Non-goals

- Full Python semantic proof.
- Whole-program soundness.
- Arbitrary plugin systems.
- Runtime monkey patch safety.
- Complete static type inference.
- Complete descriptor, metaclass, import-hook, or native-extension modeling.

## Reproducibility

Run:

```powershell
python -m benchmarks.runner --format json --output benchmark-results.json
python -m benchmarks.runner --format markdown --output benchmark-report.md
python tools/check_evidence.py benchmark-results.json
```

CI uploads `benchmark-results.json`, `benchmark-report.md`, and
`coverage.xml` as safety evidence artifacts.

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 