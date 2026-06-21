"""Execution-path specialization helpers.

This module is intentionally a thin first step toward a specialized Python code
generator. It keeps the existing Oracle/Closure/Planner assets usable while
adding target resolution, runtime call graph capture, code emission, and output
verification around a generated ``specialized()`` entry point.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libcst as cst

from flatten._cli_io import _entry_func, _load_module, _read
from flatten.tracer import Tracer


@dataclass(frozen=True)
class ResolvedTarget:
    """Runtime object resolved from a user target specification."""

    spec: str
    value: Any
    qualname: str


@dataclass(frozen=True)
class CallGraphEdge:
    """Observed runtime call edge."""

    caller: str
    callee: str
    receiver_type: str


@dataclass(frozen=True)
class SpecializationResult:
    """Generated specialization artifact plus runtime evidence."""

    source: str
    call_graph: tuple[CallGraphEdge, ...]
    verified: bool


class TargetResolver:
    """Resolve ``module:function`` or dotted ``Class.method`` specs."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.module = _load_module(self.path, f"_flatten_target_{self.path.stem}")

    def resolve(self, spec: str) -> ResolvedTarget:
        if ":" in spec:
            _, _, qualname = spec.partition(":")
        else:
            qualname = spec
        if not qualname:
            raise ValueError("target must be module:function or dotted object path")
        value = self.module
        for part in qualname.split("."):
            try:
                value = getattr(value, part)
            except AttributeError as exc:
                raise ValueError(f"target not found: {spec}") from exc
        return ResolvedTarget(spec=spec, value=value, qualname=qualname)


class CallGraphBuilder:
    """Build a runtime call graph by executing the entry with concrete inputs."""

    def build(
        self,
        entry: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[CallGraphEdge, ...]:
        with Tracer(target=entry) as tracer:
            entry(*args, **kwargs)
        edges = []
        previous = getattr(entry, "__qualname__", getattr(entry, "__name__", "<entry>"))
        for record in tracer.records:
            receiver_type = (
                f"{record.impl_class.__module__}.{record.impl_class.__qualname__}"
                if record.impl_class is not None
                else ""
            )
            edges.append(
                CallGraphEdge(
                    caller=previous,
                    callee=record.qualname,
                    receiver_type=receiver_type,
                )
            )
            previous = record.qualname
        return tuple(edges)


class PartialEvaluator:
    """Convert concrete entry arguments into Python source literals."""

    def entry_call(self, function_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        values = [_python_literal(arg) for arg in args]
        values.extend(f"{name}={_python_literal(value)}" for name, value in kwargs.items())
        return f"{function_name}({', '.join(values)})"


class ConstantFolder:
    """Fold constants in generated code using CPython's AST compiler path."""

    def fold_source(self, source: str) -> str:
        # LibCST remains the emission format; this is a placeholder for later
        # expression-level folding once inlining produces foldable expressions.
        cst.parse_module(source)
        return source


class CodeEmitter:
    """Emit a standalone module with a ``specialized()`` function."""

    def emit(self, source: str, specialized_call: str) -> str:
        module = cst.parse_module(source)
        specialized = cst.parse_statement(
            f"def specialized():\n"
            f"    return {specialized_call}\n"
        )
        emitted = module.with_changes(body=tuple(module.body) + (specialized,))
        return emitted.code


class Verifier:
    """Compare original entry execution with generated ``specialized`` execution."""

    def verify(
        self,
        original_entry: Any,
        generated_path: Path,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> bool:
        generated = _load_module(
            generated_path.resolve(),
            f"_flatten_generated_{generated_path.stem}",
        )
        original_value = original_entry(*args, **kwargs)
        generated_value = generated.specialized()
        if original_value != generated_value:
            raise AssertionError(
                f"specialized output mismatch: {original_value!r} != {generated_value!r}"
            )
        return True


class FunctionInliner:
    """Placeholder boundary for future LibCST function and method inlining."""

    def inline(self, source: str, call_graph: tuple[CallGraphEdge, ...]) -> str:
        cst.parse_module(source)
        return source


class DispatchEliminator:
    """Placeholder boundary for future observed dispatch rewrites."""

    def eliminate(self, source: str, call_graph: tuple[CallGraphEdge, ...]) -> str:
        cst.parse_module(source)
        return source


def load_args_json(path: Path) -> tuple[tuple[Any, ...], dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        args = raw.get("args", [])
        kwargs = raw.get("kwargs", {})
    elif isinstance(raw, list):
        args = raw
        kwargs = {}
    else:
        raise ValueError("--args-json must be an object or an array")
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        raise ValueError("--args-json args must be array and kwargs must be object")
    return tuple(args), dict(kwargs)


def expand_target(path: Path, target: str) -> str:
    resolved = TargetResolver(path).resolve(target)
    try:
        return inspect.getsource(resolved.value)
    except (OSError, TypeError) as exc:
        raise ValueError(f"cannot expand target source: {target}") from exc


def specialize_source(
    path: Path,
    entry_spec: str,
    target_spec: str,
    args_path: Path,
    out_path: Path,
) -> SpecializationResult:
    path = path.resolve()
    out_path = out_path.resolve()
    args, kwargs = load_args_json(args_path.resolve())
    TargetResolver(path).resolve(target_spec)
    entry = _entry_func(path, entry_spec, "_specialize_entry")
    graph = CallGraphBuilder().build(entry, args, kwargs)

    function_name = entry_spec.partition(":")[2]
    source = _read(path)
    source = DispatchEliminator().eliminate(source, graph)
    source = FunctionInliner().inline(source, graph)
    specialized_call = PartialEvaluator().entry_call(function_name, args, kwargs)
    emitted = CodeEmitter().emit(source, specialized_call)
    emitted = ConstantFolder().fold_source(emitted)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(emitted, encoding="utf-8")
    verified = Verifier().verify(entry, out_path, args, kwargs)
    return SpecializationResult(source=emitted, call_graph=graph, verified=verified)


def _python_literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if value is True:
        return "True"
    if value is False:
        return "False"
    if value is None:
        return "None"
    if isinstance(value, list):
        return "[" + ", ".join(_python_literal(item) for item in value) + "]"
    if isinstance(value, tuple):
        inner = ", ".join(_python_literal(item) for item in value)
        if len(value) == 1:
            inner += ","
        return f"({inner})"
    if isinstance(value, dict):
        items = [
            f"{_python_literal(key)}: {_python_literal(item)}"
            for key, item in value.items()
        ]
        return "{" + ", ".join(items) + "}"
    return repr(value)
