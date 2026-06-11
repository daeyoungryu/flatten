# Limitations

- Runtime tracing currently maps CLI observations to static call sites using source discovery and method-name order as a Python 3.10-compatible fallback.
- Guarded dispatch is emitted as an expression-level rewrite only when the receiver is a simple name.
- Import insertion is intentionally conservative; inaccessible class references cause no plan rather than an unsafe import rewrite.
- The verifier cannot automatically detect arbitrary filesystem, network, database, or global process side effects.
- Native Windows mutation testing is not supported by `mutmut`.
