# Safety Model

Runtime observation is evidence, not proof. Verification only replays observed
inputs and compares behavior for those inputs. It cannot prove that unobserved
receiver types, future subclasses, dynamic imports, monkey patches, or different
inputs preserve behavior.

The default policy is conservative:

- Rewrite only with positive CLOSED evidence: `typing.final`, an explicit sealed
  allowlist, or a completed closed-world scan.
- Treat OPEN, UNKNOWN, UNSAFE, and UNSUPPORTED cases as rejected.
- Prefer transparent refusal over a plausible but unsound rewrite.
- Run behavior verification in subprocesses with a Windows-compatible
  `subprocess.run(timeout=...)` timeout.

The subprocess harness compares stdout, stderr, return values, exception type
and message, and configured side effects. Passing verification means the
observed inputs matched; it is not proof for unobserved inputs.
