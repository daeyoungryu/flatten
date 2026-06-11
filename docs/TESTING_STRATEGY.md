# Testing Strategy

The test strategy favors safe rejection over optimistic rewriting. Observation
is evidence, not proof, so tests assert that uncertain inputs remain refused.

- Regression tests cover known D1-D4 soundness defects.
- Phase 2 reason-code tests verify structured refusal transparency.
- `tests/differential/` contains 20 policy fixtures. Each case parses the
  transformed candidate input, checks the expected allow/refuse policy, and
  validates the reason code rather than comparing golden output bytes.
- Negative tests simulate safety-critical mutations such as forcing OPEN
  verdicts to CLOSED or allowing dynamic getattr.
- Hypothesis fuzz tests generate simple hierarchies and method names to verify
  no crashes and conservative rejection for hidden subclasses.
- Build and wheel smoke tests verify packaging, import, and CLI entry points.
