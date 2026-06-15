"""Closure analysis for observed polymorphic implementations."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections import deque
from dataclasses import dataclass, field
from types import FunctionType

from flatten.contracts import ClosureStatus, ClosureVerdict


@dataclass(frozen=True)
class ClosureConfig:
    sealed_roots: set[str] = field(default_factory=set)
    allow_final: bool = True
    closed_world: bool = False
    package_prefixes: tuple[str, ...] = ()
    static_known_classes: frozenset[str] = frozenset()
    static_subclasses: dict[str, set[str]] = field(default_factory=dict)
    use_runtime_subclasses_for_closure: bool = True


def get_all_subclasses(cls: type) -> list[type]:
    """Return every subclass below cls, including indirect descendants."""
    result: list[type] = []
    queue: deque[type] = deque(cls.__subclasses__())
    while queue:
        subclass = queue.popleft()
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


def _raw_attr_for(cls: type, method_name: str) -> object | None:
    for item in cls.__mro__:
        if method_name in item.__dict__:
            attr: object = item.__dict__[method_name]
            return attr
    return None


def _observed_methods(method_name: str, observed_impls: list[type]) -> list[FunctionType]:
    methods: list[FunctionType] = []
    for cls in observed_impls:
        method = _method_for(cls, method_name)
        if method is not None and method not in methods:
            methods.append(method)
    return methods


def _check_os1(methods: list[FunctionType]) -> str | None:
    """Signal OS1: method closes over free variables captured from an enclosing scope."""
    for method in methods:
        if method.__code__.co_freevars:
            return f"OS1: free variables in {method.__qualname__}"
    return None


def _check_os2(methods: list[FunctionType]) -> str | None:
    """Signal OS2: method has active closure cells bound to enclosing local variables."""
    for method in methods:
        if method.__closure__:
            return f"OS2: closure cells in {method.__qualname__}"
    return None


def _get_method_ast(method: FunctionType) -> ast.Module | None:
    """Return the parsed AST for *method*'s source, or None when unavailable."""
    try:
        source = textwrap.dedent(inspect.getsource(method))
        return ast.parse(source)
    except (OSError, TypeError, SyntaxError, IndentationError):
        return None


def _check_os3(methods: list[FunctionType]) -> str | None:
    """Signal OS3: method writes to a nonlocal (free) variable."""
    import dis
    for method in methods:
        freevars = set(method.__code__.co_freevars)
        if not freevars:
            continue
        tree = _get_method_ast(method)
        if tree is not None:
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Store)
                    and node.id in freevars
                ):
                    return (
                        f"OS3: nonlocal write in {method.__qualname__}; "
                        "captured state can change dispatch behavior"
                    )
        else:
            # Bytecode fallback: STORE_DEREF on a freevar indicates nonlocal write.
            for instr in dis.get_instructions(method.__code__):
                if instr.opname == "STORE_DEREF" and instr.argval in freevars:
                    return (
                        f"OS3: nonlocal write in {method.__qualname__}; "
                        "captured state can change dispatch behavior"
                    )
    return None


def _check_os4(methods: list[FunctionType]) -> str | None:
    """Signal OS4: method writes instance attributes on self."""
    import dis
    for method in methods:
        tree = _get_method_ast(method)
        if tree is not None:
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.ctx, (ast.Store, ast.Del))
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                ):
                    return (
                        f"OS4: instance attribute write in {method.__qualname__}; "
                        "receiver state can change later dispatch behavior"
                    )
        else:
            # Bytecode fallback: STORE_ATTR preceded by LOAD_FAST 'self'.
            instrs = list(dis.get_instructions(method.__code__))
            for i, instr in enumerate(instrs):
                if (
                    instr.opname == "STORE_ATTR"
                    and i > 0
                    and instrs[i - 1].opname == "LOAD_FAST"
                    and instrs[i - 1].argval == "self"
                ):
                    return (
                        f"OS4: instance attribute write in {method.__qualname__}; "
                        "receiver state can change later dispatch behavior"
                    )
    return None


def _state_read_evidence(methods: list[FunctionType]) -> list[str]:
    import dis
    evidence: list[str] = []
    for method in methods:
        tree = _get_method_ast(method)
        if tree is not None:
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.ctx, ast.Load)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                ):
                    evidence.append(
                        f"STATE_READ: instance attribute read in {method.__qualname__}; "
                        "requires harness verification"
                    )
                    break
        else:
            # Bytecode fallback: LOAD_ATTR preceded by LOAD_FAST 'self'.
            instrs = list(dis.get_instructions(method.__code__))
            for i, instr in enumerate(instrs):
                if (
                    instr.opname == "LOAD_ATTR"
                    and i > 0
                    and instrs[i - 1].opname == "LOAD_FAST"
                    and instrs[i - 1].argval == "self"
                ):
                    evidence.append(
                        f"STATE_READ: instance attribute read in {method.__qualname__}; "
                        "requires harness verification"
                    )
                    break
    return evidence


def _check_os5(base_cls: type, observed_impls: list[type]) -> str | None:
    missing = [cls for cls in get_all_subclasses(base_cls) if cls not in observed_impls]
    if missing:
        names = ", ".join(cls.__qualname__ for cls in missing)
        return f"OS5: unobserved subclasses: {names}"
    return None


def _static_descendants(root: str, subclasses: dict[str, set[str]]) -> set[str]:
    descendants: set[str] = set()
    queue: deque[str] = deque(subclasses.get(root, set()))
    while queue:
        item = queue.popleft()
        if item in descendants:
            continue
        descendants.add(item)
        queue.extend(subclasses.get(item, set()))
    return descendants


def _check_static_subclasses(
    base_cls: type,
    observed_impls: list[type],
    config: ClosureConfig,
) -> str | None:
    base_name = _qualname(base_cls)
    if base_name not in config.static_known_classes:
        return "OS5: static class graph missing declared owner"
    observed_names = {_qualname(cls) for cls in observed_impls}
    missing = sorted(_static_descendants(base_name, config.static_subclasses) - observed_names)
    if missing:
        return f"OS5: unobserved static subclasses: {', '.join(missing)}"
    return None


def _qualname(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _is_final(obj: object) -> bool:
    """Check if object is marked as final via typing.final decorator (Python 3.8+)."""
    return bool(getattr(obj, "__final__", False))


def _risk_signals(base_cls: type, observed_impls: list[type], method_name: str) -> list[str]:
    signals: list[str] = []
    for cls in {base_cls, *observed_impls}:
        overrides_getattribute = (
            "__getattribute__" in cls.__dict__
            and cls.__dict__["__getattribute__"] is not object.__getattribute__
        )
        if overrides_getattribute:
            signals.append(f"UNSAFE: __getattribute__ override in {_qualname(cls)}")
        if "__getattr__" in cls.__dict__:
            signals.append(f"UNSAFE: __getattr__ override in {_qualname(cls)}")
        if "__setattr__" in cls.__dict__:
            signals.append(f"UNSAFE: __setattr__ override in {_qualname(cls)}")
        if "__delattr__" in cls.__dict__:
            signals.append(f"UNSAFE: __delattr__ override in {_qualname(cls)}")
        if "__init_subclass__" in cls.__dict__:
            signals.append(f"UNSAFE: __init_subclass__ hook in {_qualname(cls)}")
        if type(cls) is not type:
            signals.append(f"UNSAFE: custom metaclass in {_qualname(cls)}")
        user_bases = [
            base
            for base in cls.__bases__
            if base is not object and base.__module__ != "builtins"
        ]
        if len(user_bases) > 1:
            signals.append(f"UNSAFE: multiple inheritance in {_qualname(cls)}")

        raw_attr = cls.__dict__.get(method_name)
        if isinstance(raw_attr, property) or (
            raw_attr is not None
            and hasattr(raw_attr, "__get__")
            and not isinstance(raw_attr, (FunctionType, staticmethod, classmethod))
        ):
            signals.append(
                f"UNSAFE: descriptor/property dispatch in {_qualname(cls)}.{method_name}"
            )

        method = _method_for(cls, method_name)
        raw_attr = cls.__dict__.get(method_name)
        if (
            raw_attr is not None
            and method is not None
            and not method.__qualname__.startswith(f"{cls.__qualname__}.")
        ):
            signals.append(f"UNSAFE: possible monkey patch on {_qualname(cls)}.{method_name}")
    for method in _observed_methods(method_name, observed_impls):
        signals.extend(_method_dynamic_hazards(method))
    return signals


_DANGEROUS_NAMES: frozenset[str] = frozenset({"eval", "exec", "__import__"})


def _method_dynamic_hazards(method: FunctionType) -> list[str]:
    signals: list[str] = []
    tree = _get_method_ast(method)

    if tree is not None:
        # AST path: detect import statements inside the function body.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                signals.append(
                    f"UNSAFE: dynamic import in {method.__qualname__}; "
                    "import-time side effects can change dispatch behavior"
                )
                break
        # AST path: detect eval / exec / __import__ referenced from global namespace.
        local_names = set(method.__code__.co_varnames)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Name)
                and node.id in _DANGEROUS_NAMES
                and node.id not in local_names
            ):
                signals.append(
                    f"UNSAFE: dynamic code execution in {method.__qualname__}; "
                    "runtime code can change dispatch behavior"
                )
                break
    else:
        # Bytecode fallback: source unavailable (cross-session or compiled-only).
        # co_names contains all global/builtin names referenced by the code object.
        import dis
        code = method.__code__
        if set(code.co_names) & _DANGEROUS_NAMES:
            signals.append(
                f"UNSAFE: dynamic code execution in {method.__qualname__}; "
                "runtime code can change dispatch behavior"
            )
        if any(instr.opname == "IMPORT_NAME" for instr in dis.get_instructions(code)):
            signals.append(
                f"UNSAFE: dynamic import in {method.__qualname__}; "
                "import-time side effects can change dispatch behavior"
            )

    return signals


def _external_boundary_signals(
    classes: set[type],
    package_prefixes: tuple[str, ...],
) -> list[str]:
    if not package_prefixes:
        return []
    signals: list[str] = []
    for cls in classes:
        if not cls.__module__.startswith(package_prefixes):
            signals.append(f"OPEN: external module boundary for {_qualname(cls)}")
    return signals


def _declared_owner(
    method_qualname: str,
    observed_impls: list[type],
    method_name: str,
) -> type:
    """Return the common MRO class that declares method_name."""
    if len(observed_impls) == 1:
        # Anchor to the topmost (root) class that declares method_name so that
        # OS5 checks the full subclass tree of the real base, not just the leaf.
        for cls in reversed(observed_impls[0].__mro__):
            if method_name in cls.__dict__ and cls is not object:
                return cls
    common_mro = list(observed_impls[0].__mro__)
    for observed in observed_impls[1:]:
        observed_mro = set(observed.__mro__)
        common_mro = [cls for cls in common_mro if cls in observed_mro]
    for cls in common_mro:
        if method_name in cls.__dict__:
            return cls
    for cls in observed_impls[0].__mro__:
        if method_name in cls.__dict__:
            return cls
    return observed_impls[0]


class ClosureChecker:
    def __init__(self, config: ClosureConfig | None = None) -> None:
        self.config = config or ClosureConfig()

    def check(self, method_qualname: str, observed_impls: list[type]) -> ClosureVerdict:
        if not observed_impls and self.config.sealed_roots:
            return ClosureVerdict(
                method_qualname=method_qualname,
                known_impls=[],
                open_signals=[],
                signal="UNKNOWN",
                rationale="explicit sealed roots require observed implementations",
                status=ClosureStatus.UNKNOWN,
                blockers=("no observed impls",),
                evidence=("explicit sealed root allowlist present",),
            )

        if not observed_impls:
            return ClosureVerdict(
                method_qualname,
                False,
                [],
                ["no observed impls"],
                "OPEN",
                "cannot prove closed without observed implementations",
                status=ClosureStatus.OPEN,
                blockers=("no observed impls",),
                evidence=("checked observed implementations",),
            )

        method_name = method_qualname.rsplit(".", 1)[-1]
        base_cls = _declared_owner(method_qualname, observed_impls, method_name)
        declared_method_qualname = f"{base_cls.__qualname__}.{method_name}"

        methods = _observed_methods(method_name, observed_impls)
        external = _external_boundary_signals(
            {base_cls, *observed_impls},
            self.config.package_prefixes,
        )
        if external:
            return ClosureVerdict(
                method_qualname=declared_method_qualname,
                is_closed=False,
                known_impls=list(observed_impls),
                open_signals=external,
                signal="OPEN",
                rationale="cannot prove closed across external module boundary",
                status=ClosureStatus.OPEN,
                blockers=tuple(external),
                evidence=("checked package boundary",),
            )

        unsafe = _risk_signals(base_cls, observed_impls, method_name)
        if unsafe:
            unsafe.append(
                "OPEN: finite runtime observation cannot prove closed; "
                "__subclasses__ misses unimported and future dynamic classes"
            )
            return ClosureVerdict(
                method_qualname=declared_method_qualname,
                is_closed=False,
                known_impls=list(observed_impls),
                open_signals=unsafe,
                signal="UNSAFE",
                rationale=(
                    "cannot prove closed: dynamic dispatch risks prevent "
                    "behavior-preserving rewrite"
                ),
                status=ClosureStatus.UNSAFE,
                blockers=tuple(unsafe),
                evidence=("checked dynamic dispatch hazards",),
            )

        subclass_signal = (
            _check_static_subclasses(base_cls, observed_impls, self.config)
            if self.config.static_known_classes
            else _check_os5(base_cls, observed_impls)
            if self.config.use_runtime_subclasses_for_closure
            else "OS5: static class graph unavailable"
        )
        open_signals = [
            signal
            for signal in (
                _check_os1(methods),
                _check_os2(methods),
                _check_os3(methods),
                _check_os4(methods),
                subclass_signal,
            )
            if signal is not None
        ]
        evidence = [
            "checked free variables",
            "checked closure cells",
            "checked nonlocal writes",
            "checked instance attribute writes",
            "checked static package subclasses"
            if self.config.static_known_classes
            else "checked runtime subclasses",
            *_state_read_evidence(methods),
        ]

        known_names = {_qualname(cls) for cls in {base_cls, *observed_impls}}
        raw_method = _raw_attr_for(base_cls, method_name)
        final_closed = self.config.allow_final and (
            _is_final(base_cls)
            or _is_final(raw_method)
        )
        sealed_closed = bool(known_names & self.config.sealed_roots)
        closed_world = self.config.closed_world and not open_signals

        if not open_signals and (final_closed or sealed_closed or closed_world):
            if final_closed:
                reason = "typing.final class or method"
            elif sealed_closed:
                reason = "explicit sealed root allowlist"
            else:
                reason = "closed-world package scan"
            return ClosureVerdict(
                method_qualname=declared_method_qualname,
                is_closed=True,
                known_impls=list(observed_impls),
                open_signals=[],
                signal="CLOSED",
                rationale=reason,
                status=ClosureStatus.CLOSED,
                reasons=(reason,),
                evidence=tuple(evidence),
            )

        if not open_signals:
            reason = (
                "local hierarchy complete in available runtime/static graph, "
                "but no positive closure evidence"
            )
            return ClosureVerdict(
                method_qualname=declared_method_qualname,
                is_closed=False,
                known_impls=list(observed_impls),
                open_signals=[],
                signal="PROBABLY_CLOSED",
                rationale=reason,
                status=ClosureStatus.PROBABLY_CLOSED,
                reasons=(reason,),
                evidence=tuple(evidence),
            )
        signal = "OPEN"
        return ClosureVerdict(
            method_qualname=declared_method_qualname,
            is_closed=False,
            known_impls=list(observed_impls),
            open_signals=open_signals,
            signal=signal,
            rationale="cannot prove closed from static and observed evidence",
            status=ClosureStatus.OPEN,
            blockers=tuple(open_signals),
            evidence=tuple(evidence),
        )
