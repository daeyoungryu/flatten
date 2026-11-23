# flatten-polymorph

`flatten-polymorph` is an experimental Python 3.8+ library for turning polymorphic method calls into explicit direct calls or guarded dispatch expressions when runtime observation and static checks suggest that the call site is closed. It is an observation-based heuristic, not a soundness proof.

The package is meant to be conservative. Observation is evidence, not proof. A rewrite is emitted only when the call site, observed implementation set, and closure verdict agree that the target looks closed. The intended default policy is safe reject: when closure is unclear, the tool should refuse to rewrite.

**Status: experimental.** An independent full-code review in November 2026 found many cases where this intent is not met. The localized ones are fixed and covered by regression tests; the structural ones are listed under [Known Limitations](#known-limitations). Do not rely on a rewrite without reviewing the diff and running your own tests.

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

`flatten-polymorph` is not published on PyPI yet. Install it from GitHub:

```powershell
pip install "git+https://github.com/daeyoungryu/flatten.git"
python -m flatten --help
```

Or install from a source checkout:

```powershell
git clone https://github.com/daeyoungryu/flatten.git
cd flatten
pip install .
python -m flatten --help
```

Import names:

- Distribution name: `flatten-polymorph`
- Implementation import and CLI module: `flatten`
- Compatibility shim: `flatten_polymorph`

Supported Python versions: 3.8 minimum. Python 3.12+ uses `sys.monitoring`;
Python 3.8 through 3.11 use the `sys.settrace` fallback.

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

The checker is designed to leave a call site unrevised when it cannot establish closure (see Known Limitations for gaps).

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
flatten rewrite examples/simple_closed_single.py --plan /tmp/fp_plan.json --out /tmp/fp_rewritten.py --apply --skip-verify
flatten verify examples/simple_closed_single.py /tmp/fp_rewritten.py --entry examples.simple_closed_single:main
flatten report /tmp/fp_plan.json
```

All commands print JSON with a short summary. `analyze` also supports `--format html`.
Use `--strict` to turn unsafe or unbound evidence into a non-zero exit where
the command supports it. `rewrite` is dry-run by default; pass `--apply` to
write output. `rewrite --apply` must either verify the result (`--entry module:function`
together with `--cases cases.json`, a JSON list of `{"args": [...], "kwargs": {...}}`)
or opt out with `--skip-verify`; you can run `flatten verify` separately afterwards, as above.
Source files may be saved with a UTF-8 BOM.

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

## Known Limitations

These are known gaps where flatten can still approve a rewrite that changes behavior, or where its checks are weaker than the documentation above may suggest. They were found by an independent code review and are not fixed yet.

Receiver and closure checks:

- A call on a non-variable receiver, such as `factory().run()`, can still be turned into a direct call after seeing only one type.
- A name can be shadowed (for example by a parameter default like `def main(A=A)`), and a class can fake `__class__`, which can fool the guarded fallback.
- The closed-world scan can miss subclasses created through aliases such as `import m; P = m.Base`, or an alias in the same file.
- Some class hooks are not detected everywhere: `__getattribute__` on a base class, writes to an instance through an alias, and a final leaf class that overrides a final root method.
- A verdict for one class hierarchy can wrongly approve a call site that belongs to another hierarchy.

Generated code:

- Guarded dispatch can be missing parentheses inside large expressions, can use a temporary variable in a place where it is not defined, can crash on generator arguments such as `f(i for i in x)`, and can change the message of an error raised for `*args`.

Trust and files:

- Saved plan files are checked for accidental edits only. They are not signed, so a plan that was deliberately forged and given a fresh digest would be accepted.
- Observation files that were written by older versions (no `source_hash`) are still accepted without a warning, and a type reference inside an observation file can import a module while planning.
- `verify` and `rewrite --apply` run your module in the same process as flatten. This is not a sandbox and not a separate-process check.

Verification:

- A cases file may contain `effect_expression`; it is currently read and ignored.
- Exceptions are compared by class name and message, not by identity of the class. Types inside containers (for example `[True]` versus `[1]`) are not compared.
- Behavior checks run on copies of the inputs, so code that depends on object identity can pass verification and still behave differently. Code that depends on the name of the directory it is published in can also differ.
- Passing verification covers only the inputs you gave it.

Tracing and platforms:

- Errors raised by `__deepcopy__` or `__repr__` while values are captured can escape the tracer. Async entry points produce empty evidence.
- All checks so far were run on Windows with Python 3.12. Python 3.8 to 3.11 (the `sys.settrace` backend) and other operating systems are not verified.

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

## Benchmark And Release Evidence

The OSS benchmark catalog is tracked in `benchmarks/projects.csv` and currently
contains 35 public Python projects. The local benchmark sanity command emits
JSON and Markdown summaries:

```powershell
python -m flatten benchmark --catalog benchmarks/projects.csv --out-json benchmarks/summary.json --out-md benchmarks/summary.md
```

Current quantitative status:

| KPI | Value |
| --- | --- |
| Project Catalog Size | 35 |
| Projects Evaluated | 0 |
| Total Call Sites | 0 |
| Candidates | 0 |
| Rewritten | 0 |
| Rejected | 0 |
| Unsafe | 0 |
| Unknown | 0 |
| False Positives | 0 |
| Behavior Mismatches | 0 |
| Proof Coverage | n/a |
| Closure Coverage | n/a |

This is a catalog and gate status, not a completed 30-project empirical run.
Release 0.2.0 remains blocked until the release criteria in
`docs/research_evaluation.md` are satisfied.
