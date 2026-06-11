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

## DEC-006 | 2026-06-10 | CLOSED Requires Explicit Evidence

Decision: Allow CLOSED verdicts only for final classes/methods, explicit sealed
allowlists, closed-world scans, or complete local hierarchies with no risk
signals.

Reason: Runtime observation alone is finite evidence and must not justify a
rewrite. The project needs to rewrite real safe cases without turning every
unknown into an unsafe transform.

Impact: `ClosureChecker` now returns `CLOSED`, `OPEN`, or `UNSAFE`. Monkey
patching, dynamic attribute lookup, descriptors/properties, custom metaclasses,
and multiple inheritance block rewrites.

## DEC-007 | 2026-06-10 | CLI Reports the Full Pipeline

Decision: Implement `flatten analyze`, `trace`, `plan`, `rewrite`, and `verify`
as JSON-reporting commands.

Reason: The package must demonstrate a working end-to-end flow from source
input through behavior verification, not just expose library helpers.

Impact: `src/flatten/cli.py` is no longer a placeholder. `examples/simple.py`
and `examples/simple_obs.json` serve as the smoke-test fixture.

## DEC-008 | 2026-06-10 | Structured Observation Identity

Decision: Add `TypeRef` and `FunctionRef` as canonical observation identities
while keeping legacy string parsing as compatibility input.

Reason: Safety decisions must not depend on receiver type strings alone. The
tool needs module, qualname, file, and function line evidence for reviewable
plans.

Impact: `observations.py`, `planner.py`, and CLI trace/plan now operate on
structured records.

## DEC-009 | 2026-06-10 | Refuse Guarded Dispatch for Complex Receivers

Decision: Guarded dispatch rewrites are emitted only when the receiver
expression is a simple name.

Reason: Expression-level guarded dispatch otherwise evaluates receivers such as
`factory().run()` multiple times. Until statement-level temporary-variable
rewrites exist, refusal is the safer behavior.

Impact: `RewritePlanner.plan_from_observations` skips multi-implementation
plans for non-name receivers.

## DEC-010 | 2026-06-11 | Unsafe Input Never Becomes CLOSED in CLI

Decision: CLI planning must not infer sealed roots from observations. Observed
receiver types are restored as live type objects before calling
`ClosureChecker`; failed restoration produces UNKNOWN, not CLOSED. External
plan files are untrusted unless they carry a matching source hash and serialized
CLOSED evidence.

Reason: A CLI path that bypasses `ClosureChecker` invalidates the safety model.
Plan files are external input and cannot manufacture a CLOSED verdict.

Impact: `flatten trace` records caller frame locations, `flatten plan` excludes
unbound observations from rewrite planning, and `flatten rewrite` writes only
with explicit `--apply`.

## DEC-011 | 2026-06-11 | Mandatory Type Check Scope Is Source Package

Decision: Keep `mypy .` as a required command, but configure mypy to exclude
`tests/` and `examples/` so strict type checking applies to the distributable
source package.

Reason: Phase 0 requires a stable source typing gate. Existing tests and
examples intentionally contain dynamic fixtures, monkey patching, and untyped
sample code that should be exercised by pytest/ruff rather than strict mypy.

Impact: `python -m mypy .` now reports success for the 18 source files while
pytest continues to execute the full test suite.

## DEC-012 | 2026-06-11 | Rewrite Authorization Is a First-Class Decision

Decision: Add `RewriteDecision` as the explicit allow/refuse contract derived
from `ClosureVerdict.status`, blockers, evidence, and confidence.

Reason: `TransformPlan` describes a rewrite that can be applied, but it does
not explain refused rewrites. Safety review needs a stable record for both
allowed and rejected decisions.

Impact: `RewritePlanner.decide()` returns decision records, CLI JSON includes
`rewrite_decisions`, and planning uses the decision's `allowed` flag instead of
raw `is_closed` checks.

## DEC-013 | 2026-06-11 | Type Restoration Must Avoid Stale Module Cache

Decision: When CLI restores observed types and has a fallback source path, it
reloads the module if the cached `sys.modules` entry points at another file.

Reason: Tests and repeated CLI-style operations can reuse common module names
such as `case`, and stale type objects can turn an unsafe verdict into a stale
closed decision.

Impact: `_restore_type()` compares cached module `__file__` with the fallback
path before reusing the module.

## DEC-014 | 2026-06-11 | Dynamic Runtime Hooks Are UNSAFE Blockers

Decision: Treat `__setattr__`, `__delattr__`, `__init_subclass__`, dynamic code
execution, and method-local imports as UNSAFE blockers for rewrite planning.

Reason: These hooks can mutate receiver state, subclass availability, or module
state outside the observed call path. A final class/method annotation cannot
make those effects behavior-preserving for a source rewrite.

Impact: `ClosureChecker` refuses these cases even when `@final` evidence is
present, and `static.py` reports matching risk flags for review output.

## DEC-015 | 2026-06-11 | Release Claims Require a Test Map

Decision: Track public safety and CLI claims in `docs/claim_test_map.md` and
keep representative examples in `docs/golden_corpus.md`.

Reason: A safety-oriented rewrite tool needs reviewable evidence for each
claim. Tests passing is necessary but not sufficient unless reviewers can see
which test protects which claim.

Impact: Release-quality tests now require the claim map, golden corpus, README
safety language, and CI verification commands to stay present.

## DEC-016 | 2026-06-11 | Bind Same-Line Calls With Runtime Columns

Decision: Record caller source columns from bytecode instruction positions and
use them to disambiguate multiple method calls on the same line.

Reason: Caller line alone is insufficient for expressions such as
`left.run() + right.run()`. Treating those observations as unbound leaves safe
evidence unusable and makes plan output less precise.

Impact: `OracleRecord` includes `caller_column` and `caller_end_column`, and
CLI trace binding filters same-line candidates by column when available.

## DEC-017 | 2026-06-11 | Guarded Dispatch Uses Temps for Complex Receivers

Decision: Allow guarded dispatch for non-name receivers only when the rewrite
can introduce a temporary receiver binding at statement level.

Reason: Expression-level guarded dispatch would evaluate receivers such as
`make().run()` multiple times. A temp assignment preserves single evaluation
for supported return-statement rewrites.

Impact: `TransformPlan` carries temp receiver metadata, `planner.py` emits
`guarded_temp`, and `transformer.py` inserts the temp assignment before the
rewritten return.

## DEC-018 | 2026-06-11 | Planner Closure Uses Static Class Graph Evidence

Decision: In CLI planner flow, pass `static.py` class graph evidence to
`ClosureChecker` and disable runtime subclass closure evidence.

Reason: Runtime `__subclasses__` evidence misses unimported classes and is not
a stable package-level proof. The planner path already has source access and
should use static class graph evidence for local hierarchy closure.

Impact: CLI verdict evidence reports `checked static package subclasses`, while
direct library use can still opt into the runtime fallback through
`ClosureConfig`.

## DEC-019 | 2026-06-11 | Applied Rewrites Must Verify or Be Explicitly Skipped

Decision: `flatten rewrite --apply` now runs harness verification before
writing the output file. The command requires `--entry` unless the user passes
`--skip-verify`, and external plan-file replacements are rejected when their
generated class names are not present in the source module scope.

Reason: A rewrite that reaches disk without behavior evidence violates the
safety contract. Plan files are external input, so source hash and CLOSED
evidence are not enough if the generated code would raise `NameError`.

Impact: DEFECT-6 is enforced in the rewrite pipeline itself, INV-7 has a
regression test, and golden safe/unsafe fixtures are executable through the
trace -> plan path.

## DEC-020 | 2026-06-11 | CLOSED Needs Positive Closure Evidence

Decision: Remove the local-complete CLOSED promotion path. Closure verdicts may
be CLOSED only when final evidence, an explicit sealed root allowlist, or a
closed-world scan is present and no blockers are found.

Reason: The absence of open signals is not proof. Static or runtime local
completeness can miss unimported, future, or wrongly scoped subclasses and can
turn an unobserved sibling override into a silent wrong rewrite.

Impact: `ClosureChecker` reports OPEN for locally complete hierarchies without
positive closure evidence, and tests now assert that unobserved siblings block
plans.

## DEC-021 | 2026-06-11 | Closure Owner Is the Declaration Owner

Decision: Compute the closure base from the relevant MRO declaration owner
rather than from the observed concrete implementation qualname.

Reason: Traces report implementations such as `Circle.area`, but dispatch
soundness depends on the declaring class whose descendants can still override
the method.

Impact: Verdict `method_qualname` now records the declaration owner, and OS5
subclass completeness checks run against that owner.

## DEC-022 | 2026-06-11 | Path Binding Is Canonical at CLI Boundaries

Decision: Resolve CLI file paths and trace caller filenames before discovery,
observation binding, planning, and rewrite.

Reason: Relative source paths and absolute runtime `co_filename` values caused
observations to become unbound silently.

Impact: Relative `trace -> plan -> rewrite` succeeds when evidence is bindable;
zero plans plus unbound observations warns on stderr, and `--strict` exits
non-zero.

## DEC-023 | 2026-06-11 | Rewrite Refusal Uses Stable Reason Codes

Decision: Extend `RewriteDecision` with structured reason codes and explanatory
metadata for both allowed and refused rewrites.

Reason: Safety review needs machine-readable refusal causes. A boolean allowed
flag and free-text blockers are not enough for policy tests, report generation,
or downstream automation.

Impact: Planner/CLI decision JSON now includes reason code, message, closure
verdict, observed receiver types, dispatch order, required imports, and safety
notes.

## DEC-024 | 2026-06-11 | Verification Runs in Subprocess Isolation

Decision: Add a subprocess-based module equivalence harness using
`subprocess.run(timeout=...)`.

Reason: In-process verification shares interpreter state and cannot provide
clean stdout/stderr/effects isolation. Windows compatibility rules also forbid
POSIX-only timeout mechanisms.

Impact: The harness compares return values, exception type/message, stdout,
stderr, and configured side effects under a timeout while documenting that this
only verifies observed inputs.

## DEC-025 | 2026-06-11 | Release Gate Is Executable and Typed

Decision: Treat Phase 3 release readiness as executable gates: compileall,
import, CLI help, pytest, ruff, mypy, build, wheel install smoke, and
check-wheel-contents.

Reason: Packaging quality is part of safety. A rewrite tool that cannot be
installed, typed, imported, or audited reliably should not be treated as a
validated transformer.

Impact: `py.typed` markers, guarded `__main__` modules, metadata classifiers,
CI jobs, report schema, release docs, and executable examples are now part of
the testable release contract.
