# Changelog

## 0.2.1

- SI hardening pass (RP/SE/P2, phases 1-4): tighten rewrite preconditions and
  side-effect detection so unclear cases fall back to safe reject.
- Restore Python 3.8 runtime compatibility: avoid import-time `Callable`
  subscripting and keep the tracer import path 3.8-safe.
- Harden tracer target scope and tracing/rewrite regressions.

## 0.2.0

- SI soundness enforcement (phases 0-6): closure verdicts must agree with the
  observed implementation set before a rewrite is emitted.
- Add the execution-path `specialize` CLI.

## 0.1.1

- Fix release-blocking module entrypoint and strict type gates.
- Harden closure and rewrite safety for probably-closed local hierarchies.
- Add built-wheel release gate for compile, CLI, mypy, and minimal e2e checks.

## 0.1.0

- Added position-based static call-site discovery.
- Added structured `TypeRef`, `FunctionRef`, and `ObservationRecord` schemas.
- Added conservative closure and rewrite planning with CLOSED/OPEN/UNSAFE verdicts.
- Added CLI flow: analyze, trace, plan, rewrite, verify, and report.
- Added behavior verification for return values, exceptions, stdout, stderr, and explicit effects.
