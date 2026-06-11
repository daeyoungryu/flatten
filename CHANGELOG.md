# Changelog

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
