# Golden Corpus

This corpus defines stable safe and unsafe examples used for release review.
Each file is intentionally small so a failed verdict can be inspected by hand.

| File | Expected | Claim |
| --- | --- | --- |
| `examples/simple_closed_single.py` | CLOSED | `typing.final` class can rewrite a direct call when the call site is bound. |
| `examples/closed_guarded.py` | CLOSED | Closed observed implementations can produce guarded dispatch for simple receivers. |
| `examples/open_unobserved_subclass.py` | OPEN | Unobserved subclasses block rewrite. |
| `examples/unsafe_monkey_patch.py` | UNSAFE | Monkey-patched methods block rewrite. |
| `examples/unsafe_getattribute.py` | UNSAFE | Dynamic attribute lookup blocks rewrite. |
| `examples/unsafe_phase2_dynamic.py` | UNSAFE | Dynamic attribute mutation hooks, subclass hooks, eval, and imports block rewrite. |
| `examples/same_shape_callsites.py` | POSITIONAL | Identical call shapes keep distinct call-site ids. |
| `examples/verify_exception_equivalence.py` | VERIFY | Verification compares exception type and message. |

The required release gate is:

```powershell
python -c "import flatten"
python -m pytest -q
python -m pytest --cov=flatten --cov-report=term-missing --cov-fail-under=90
python -m ruff check .
python -m mypy .
```
