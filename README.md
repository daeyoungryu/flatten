# flatten-polymorph

`flatten-polymorph` is an experimental Python 3.10+ library for turning positively closed polymorphic method calls into explicit direct calls or guarded dispatch expressions.

The package is intentionally conservative. Observation is evidence, not proof. A rewrite is emitted only when the call site, observed implementation set, and closure verdict agree that the target is closed. The default policy is safe reject: when closure is unclear, the tool refuses to rewrite.

## Problem

Python code often hides dispatch behind `obj.method(...)`. That flexibility is valuable, but it makes profiling, specialization, static review, and mechanical refactoring harder. This project provides an end-to-end pipeline:

```text
source code
-> call-site discovery
-> runtime observations or oracle JSON
-> closure/safety verdict
-> rewrite plan
-> LibCST source transform
-> behavior verification
-> JSON/human-readable report
```

## Quickstart

```powershell
pip install flatten-polymorph
python -m flatten --help
```

Import names:

- Distribution name: `flatten-polymorph`
- Implementation import and CLI module: `flatten`
- Compatibility shim: `flatten_polymorph`

Supported Python versions: 3.10 minimum, 3.12 recommended.

## When Rewrite Is Allowed

The planner only emits a rewrite when:

- The static call site is identified by file, line, and column.
- Observation records link that exact call site to concrete receiver types and resolved functions.
- `ClosureChecker` returns `CLOSED`.
- `RewriteDecision` records an allowed decision with no blockers.
- `rewrite` is called with explicit `--apply`.

Current CLOSED evidence includes:

- `typing.final` class or method.
- Explicit sealed root/class allowlist from observations.
- Closed-world mode over a scanned package. Single-file static analysis alone is not closure proof.
Local hierarchy completeness without positive evidence is not enough.

## OPEN and UNSAFE Cases

The checker leaves a call site unrevised when it cannot prove closure.

OPEN examples:

- Unobserved subclasses exist.
- External module boundary allows future subclasses.
- Static subclass set and observed type set disagree.
- Runtime-only evidence is finite and incomplete.

UNSAFE examples:

- Monkey-patched methods.
- `__getattribute__` or `__getattr__` overrides.
- `__setattr__`, `__delattr__`, or `__init_subclass__` hooks.
- Descriptor or `property` dispatch.
- Custom metaclass behavior.
- Dynamic code execution or dynamic imports inside observed methods.
- Multiple inheritance with complex MRO.
- Side-effectful targets unless the user explicitly treats the target as pure for verification.

## CLI

```powershell
flatten analyze examples/simple_closed_single.py --json
flatten trace examples/simple_closed_single.py --entry examples.simple_closed_single:main --out /tmp/fp_obs.json
flatten plan examples/simple_closed_single.py --observations /tmp/fp_obs.json --out /tmp/fp_plan.json
flatten rewrite examples/simple_closed_single.py --plan /tmp/fp_plan.json --out /tmp/fp_rewritten.py
flatten verify examples/simple_closed_single.py /tmp/fp_rewritten.py --entry examples.simple_closed_single:main
flatten report /tmp/fp_plan.json
```

All commands print JSON with a short summary. `analyze` also supports `--format html`.
Use `--strict` to turn unsafe or unbound evidence into a non-zero exit where
the command supports it. `rewrite` is dry-run by default; pass `--apply` to
write output.

## Observation Schema

Observation JSON is a list of records:

```json
[
  {
    "call_site_id": "examples/simple.py:12:11-12:26",
    "receiver_type": {
      "module": "examples.simple_closed_single",
      "qualname": "Worker",
      "file": "examples/simple_closed_single.py",
      "is_builtin": false
    },
    "resolved_function": {
      "module": "examples.simple_closed_single",
      "qualname": "Worker.run",
      "file": "examples/simple_closed_single.py",
      "firstlineno": 5
    },
    "method_name": "run",
    "frame_module": "examples.simple_closed_single",
    "order": 1,
    "input_hash": "call-1"
  }
]
```

The key field is `call_site_id`; it binds runtime evidence to one exact CST position.

## Before and After

Before:

```python
from typing import final

@final
class Worker:
    def run(self, value):
        return value + 1

def main():
    return Worker().run(2)
```

After:

```python
from typing import final

@final
class Worker:
    def run(self, value):
        return value + 1

def main():
    return Worker.run(Worker(), 2)
```

For multiple closed implementations, the transformer emits an expression such as:

```python
B.run(obj, 1) if isinstance(obj, B) else A.run(obj, 1) if isinstance(obj, A) else obj.run(1)
```

For a non-name receiver in a supported return statement, guarded dispatch first
stores the receiver in a temporary so the receiver is evaluated once:

```python
_flatten_receiver_1 = make()
return B.run(_flatten_receiver_1) if isinstance(_flatten_receiver_1, B) else A.run(_flatten_receiver_1) if isinstance(_flatten_receiver_1, A) else _flatten_receiver_1.run()
```

## Design Notes

- LibCST preserves formatting and applies replacements by `PositionProvider` ranges.
- `deep_equals` is not used for production rewrite targeting.
- Reports are dataclass-backed JSON structures.
- CLI planning uses static class graph evidence to find blockers; static graph completeness alone does not prove CLOSED.
- `flatten_polymorph` is provided as an import alias for the distribution name; `flatten` remains the implementation package and CLI module.
- Verification compares return values, raised exception type/message, stdout, stderr, and optional collected effects across deterministic input cases.
  Passing verification only covers observed inputs and is not proof for unobserved receiver types.

## Examples

- `examples/simple_closed_single.py`: final class, direct-call rewrite.
- `examples/closed_guarded.py`: closed hierarchy shape for guarded dispatch planning.
- `examples/open_unobserved_subclass.py`: unobserved subclass should remain OPEN.
- `examples/unsafe_monkey_patch.py`: monkey patching should remain UNSAFE.
- `examples/unsafe_getattribute.py`: dynamic attribute resolution should remain UNSAFE.
- `examples/unsafe_phase2_dynamic.py`: dynamic hooks, eval, and imports should remain UNSAFE.
- `examples/same_shape_callsites.py`: repeated `worker.run()` shapes get distinct positions.
- `examples/verify_exception_equivalence.py`: verifier compares exception type and message.

## Non-Goals

- Proving arbitrary Python dynamic dispatch sound.
- Rewriting open-world framework extension points.
- Optimizing code whose behavior depends on hidden mutable receiver state.
- Handling every descriptor, metaclass, import hook, or monkey-patching pattern beyond the documented blocker corpus.
- Applying rewrites without explicit user opt-in.

## Validation

```powershell
python -m compileall src\flatten
python -c "import flatten"
python -m flatten --help
python -m pytest -q
python -m ruff check .
python -m mypy src\flatten
python -m build
.\scripts\release_gate.ps1
```
