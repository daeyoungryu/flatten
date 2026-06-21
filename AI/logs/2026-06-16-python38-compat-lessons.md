# Python 3.8 compatibility lesson - 2026-06-16

Tags: #python38 #compatibility #import-time #typing

## Incident

`import flatten` failed on Python 3.8 while importing `src/flatten/harness.py`.

```text
EffectCollector = Callable[[], Any]
TypeError: 'ABCMeta' object is not subscriptable
```

## Root Cause

`from __future__ import annotations` only defers annotation evaluation. It does not
defer ordinary right-hand side expressions.

This means a runtime alias like this is evaluated immediately during import:

```python
from collections.abc import Callable

EffectCollector = Callable[[], Any]
```

On Python 3.8, `collections.abc.Callable` is not subscriptable, so import fails.
Use `typing.Callable` for runtime aliases that need subscription on 3.8.

## Fix Applied

- `src/flatten/harness.py` now imports `Callable` from `typing`.
- `tests/test_python38_compat.py` checks for runtime assignment RHS patterns that
  subscript `collections.abc` imports.
- The same test file also guards against `zip(strict=...)`, which is Python 3.10+.

## Checks to Repeat for Python 3.8

Run these before claiming 3.8 support:

```powershell
vermin --target=3.8 --violations src\flatten
python -m pytest tests/test_python38_compat.py tests/test_import.py tests/test_harness.py -q
python -m compileall -q src benchmarks examples
```

Also scan specifically for import-time generic evaluation:

- `Alias = Callable[..., T]` from `collections.abc`
- `Alias = list[str]`, `dict[str, T]`, `tuple[...]`, `type[T]`
- top-level or class-level RHS expressions using `A | B`

Annotations are acceptable only when the module has
`from __future__ import annotations`.
