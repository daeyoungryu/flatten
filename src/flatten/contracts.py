"""Shared data contracts for flatten's tracing and transformation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import libcst as cst


@dataclass(frozen=True)
class OracleRecord:
    qualname: str
    impl_class: type
    args: tuple
    kwargs: dict
    return_val: Any = None


@dataclass(frozen=True)
class ClosureVerdict:
    method_qualname: str
    is_closed: bool
    known_impls: list[type]
    open_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TransformPlan:
    target_node: cst.CSTNode
    replacement: cst.CSTNode
    verdict: ClosureVerdict
