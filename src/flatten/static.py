"""Static class hierarchy extraction for safety reporting."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassInfo:
    name: str
    qualname: str
    module: str
    file: str
    bases: tuple[str, ...]
    methods: frozenset[str]
    is_final: bool
    risk_flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ClassHierarchy:
    classes: dict[str, ClassInfo]
    subclasses: dict[str, set[str]]
    method_overrides: dict[str, set[str]]
    risk_flags: set[str] = field(default_factory=set)


def analyze_class_hierarchy(
    source: str,
    *,
    filename: str = "<memory>",
    module_name: str = "__main__",
) -> ClassHierarchy:
    tree = ast.parse(source, filename=filename)
    classes: dict[str, ClassInfo] = {}
    local_names: dict[str, str] = {}
    risk_flags: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            qualname = f"{module_name}.{node.name}"
            local_names[node.name] = qualname

    for walk_node in ast.walk(tree):
        if isinstance(walk_node, ast.Call) and _call_name(walk_node.func) == "setattr":
            risk_flags.add("setattr")
        if isinstance(walk_node, ast.Assign):
            for target in walk_node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in local_names
                ):
                    risk_flags.add("class-attribute-assignment")

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        qualname = f"{module_name}.{node.name}"
        methods = frozenset(
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        bases = tuple(_resolve_base(base, module_name, local_names) for base in node.bases)
        class_risks = set()
        if "__getattribute__" in methods:
            class_risks.add("__getattribute__")
        if "__getattr__" in methods:
            class_risks.add("__getattr__")
        if "__setattr__" in methods:
            class_risks.add("__setattr__")
        if "__delattr__" in methods:
            class_risks.add("__delattr__")
        if "__init_subclass__" in methods:
            class_risks.add("__init_subclass__")
        if len([base for base in bases if base != "builtins.object"]) > 1:
            class_risks.add("multiple-inheritance")
        if node.keywords:
            class_risks.add("custom-metaclass")
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_risks.update(_method_risk_flags(item))
        classes[qualname] = ClassInfo(
            name=node.name,
            qualname=qualname,
            module=module_name,
            file=filename,
            bases=bases,
            methods=methods,
            is_final=any(_decorator_name(item) == "final" for item in node.decorator_list),
            risk_flags=frozenset(class_risks),
        )

    subclasses: dict[str, set[str]] = {}
    method_overrides: dict[str, set[str]] = {}
    for info in classes.values():
        for base in info.bases:
            subclasses.setdefault(base, set()).add(info.qualname)
        for method in info.methods:
            method_overrides.setdefault(method, set()).add(info.qualname)

    return ClassHierarchy(classes, subclasses, method_overrides, risk_flags)


def _resolve_base(node: ast.expr, module_name: str, local_names: dict[str, str]) -> str:
    name = _call_name(node)
    if not name:
        return "<dynamic>"
    if name in local_names:
        return local_names[name]
    if "." in name:
        return name
    return f"{module_name}.{name}"


def _decorator_name(node: ast.expr) -> str:
    return _call_name(node.func) if isinstance(node, ast.Call) else _call_name(node)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _method_risk_flags(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    flags: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            flags.add("dynamic-import")
        if isinstance(child, ast.Call) and _call_name(child.func) in {
            "eval",
            "exec",
            "__import__",
        }:
            flags.add("dynamic-code-execution")
    return flags
