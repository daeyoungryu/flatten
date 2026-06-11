# Design

`flatten-polymorph` is organized as a pipeline:

1. `flatten.discovery` scans source with LibCST and records exact call-site ranges.
2. `flatten.tracer` records runtime method calls.
3. `flatten.observations` normalizes runtime evidence into `TypeRef` and `FunctionRef`.
4. `flatten.static` extracts class hierarchy evidence from AST.
5. `flatten.closure` classifies a dispatch as CLOSED, OPEN, UNSAFE, or UNKNOWN-style failure.
6. `flatten.planner` creates direct-call or guarded-dispatch plans only for CLOSED sites.
7. `flatten.transformer` applies LibCST rewrites by source position.
8. `flatten.harness` verifies original and rewritten behavior.

The implementation favors refusal over speculative rewriting.
