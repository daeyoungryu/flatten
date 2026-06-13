"""Runtime-aware final decorator for closure analysis."""

from __future__ import annotations

from typing import Any, TypeVar, overload
from typing import final as typing_final

T = TypeVar("T")


@overload
def final(cls: type[T], /) -> type[T]:
    ...


@overload
def final(func: T, /) -> T:
    ...


def final(obj: Any, /) -> Any:
    """Mark a class or function as final at runtime and for type checkers."""
    obj.__final__ = True
    return typing_final(obj)
