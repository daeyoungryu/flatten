"""Shared data contracts for flatten's tracing and transformation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import libcst as cst


@dataclass(frozen=True)
class OracleRecord:
    qualname: str
    impl_class: type | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    return_val: Any = None
    call_site: str = ""
    is_dispatch_target: bool = True


@dataclass(frozen=True)
class ClosureVerdict:
    method_qualname: str
    is_closed: bool
    known_impls: list[type]
    open_signals: list[str] = field(default_factory=list)
    signal: str = "CLOSED"
    rationale: str = ""


@dataclass(frozen=True)
class TransformPlan:
    target_node: cst.CSTNode
    replacement: cst.BaseExpression
    verdict: ClosureVerdict
    rationale: str = ""
    target_range: str | None = None
