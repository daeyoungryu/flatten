# Decision Log

## DEC-001 | 2026-06-10 | Freeze Shared Contracts

Decision: Move `OracleRecord`, `ClosureVerdict`, and `TransformPlan` into
`src/flatten/contracts.py` as frozen dataclasses.

Reason: The package needs stable signatures before implementation work and a
single low-level contract module avoids circular imports.

Impact: `tracer.py`, `closure.py`, `collapse.py`, and `dispatch.py` import shared
contracts from `contracts.py`.

## DEC-002 | 2026-06-10 | LibCST-Only Rewrites

Decision: Keep all generated replacement logic in LibCST expressions and
transformers.

Reason: The hard rule forbids `ast.unparse`, and LibCST preserves formatting and
statement structure such as `if`/`else` and `for` blocks.

Impact: `collapse.py` and `dispatch.py` expose LibCST-first APIs.

## DEC-003 | 2026-06-10 | One Record Shape Across Trace Paths

Decision: Use the required Python version branch (`sys.version_info >= (3, 12)`)
while sharing the OracleRecord creation path.

Reason: Python 3.12+ enables `sys.monitoring`; Python 3.8-3.11 needs fallback
tracing. Both paths must produce the same record fields.

Impact: `tracer.py` installs monitoring callbacks on 3.12+ and uses the shared
runtime trace handler to collect args, implementation class, and return value.

## DEC-004 | 2026-06-10 | Rewrite Is Opt-In

Decision: Keep rewrite capability, but make it disabled by default.

Reason: Finite runtime observation cannot prove that a polymorphic hierarchy is
closed. Automatic rewrite would be unsound.

Impact: `RewritePlanner` returns no plans unless `opt_in=True`, and rewritten
source is prefixed with an observed-based warning comment.

## DEC-005 | 2026-06-10 | Source Position Targets

Decision: Identify rewrite targets by source range metadata instead of
`deep_equals`.

Reason: Two calls can be structurally identical but refer to different source
locations. Structural equality can rewrite the wrong call site.

Impact: `TransformPlan.target_range` carries the `line:column-line:column`
identity used by `collapse_source`.
