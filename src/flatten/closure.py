"""Closure analysis for observed polymorphic implementations."""

from __future__ import annotations

import dis
from types import FunctionType

from flatten.contracts import ClosureVerdict


def get_all_subclasses(cls: type) -> list[type]:
    """Return every subclass below cls, including indirect descendants."""
    result: list[type] = []
    queue = list(cls.__subclasses__())
    while queue:
        subclass = queue.pop(0)
        result.append(subclass)
        queue.extend(subclass.__subclasses__())
    return result


def _method_for(cls: type, method_name: str) -> FunctionType | None:
    for item in cls.__mro__:
        candidate = item.__dict__.get(method_name)
        if isinstance(candidate, staticmethod):
            candidate = candidate.__func__
        elif isinstance(candidate, classmethod):
            candidate = candidate.__func__
        if isinstance(candidate, FunctionType):
            return candidate
    return None


def _observed_methods(method_name: str, observed_impls: list[type]) -> list[FunctionType]:
    methods: list[FunctionType] = []
    for cls in observed_impls:
        method = _method_for(cls, method_name)
        if method is not None and method not in methods:
            methods.append(method)
    return methods


def _check_os1(methods: list[FunctionType]) -> str | None:
    for method in methods:
        if method.__code__.co_freevars:
            return f"OS1: free variables in {method.__qualname__}"
    return None


def _check_os2(methods: list[FunctionType]) -> str | None:
    for method in methods:
        if method.__closure__:
            return f"OS2: closure cells in {method.__qualname__}"
    return None


def _check_os3(methods: list[FunctionType]) -> str | None:
    for method in methods:
        if any(instruction.opname == "STORE_DEREF" for instruction in dis.get_instructions(method)):
            return (
                f"OS3: nonlocal write in {method.__qualname__}; "
                "captured state can change dispatch behavior"
            )
    return None


def _check_os4(methods: list[FunctionType]) -> str | None:
    for method in methods:
        previous = None
        for instruction in dis.get_instructions(method):
            if (
                previous is not None
                and previous.opname == "LOAD_FAST"
                and previous.argval == "self"
                and instruction.opname in {"LOAD_ATTR", "STORE_ATTR", "DELETE_ATTR"}
            ):
                return (
                    f"OS4: instance attribute access in {method.__qualname__}; "
                    "receiver state influences behavior"
                )
            previous = instruction
    return None


def _check_os5(base_cls: type, observed_impls: list[type]) -> str | None:
    missing = [cls for cls in get_all_subclasses(base_cls) if cls not in observed_impls]
    if missing:
        names = ", ".join(cls.__qualname__ for cls in missing)
        return f"OS5: unobserved subclasses: {names}"
    return None


class ClosureChecker:
    def check(self, method_qualname: str, observed_impls: list[type]) -> ClosureVerdict:
        if not observed_impls:
            return ClosureVerdict(
                method_qualname,
                False,
                [],
                ["no observed impls"],
                "OPEN",
                "cannot prove closed without observed implementations",
            )

        method_name = method_qualname.rsplit(".", 1)[-1]
        base_cls = observed_impls[0]
        for cls in observed_impls[0].__mro__:
            if method_name in cls.__dict__:
                base_cls = cls
                break

        methods = _observed_methods(method_name, observed_impls)
        signals = [
            signal
            for signal in (
                _check_os1(methods),
                _check_os2(methods),
                _check_os3(methods),
                _check_os4(methods),
                _check_os5(base_cls, observed_impls),
            )
            if signal is not None
        ]
        signals.append(
            "OPEN: finite runtime observation cannot prove closed; "
            "__subclasses__ misses unimported and future dynamic classes"
        )
        signal = signals[0].split(":", 1)[0] if signals else "OPEN"
        return ClosureVerdict(
            method_qualname=method_qualname,
            is_closed=False,
            known_impls=list(observed_impls),
            open_signals=signals,
            signal=signal,
            rationale="cannot prove closed from finite runtime observation",
        )
