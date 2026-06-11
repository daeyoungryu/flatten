"""Shared data contracts for flatten's tracing and transformation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import libcst as cst


class ClosureStatus(Enum):
    CLOSED = "closed"
    PROBABLY_CLOSED = "probably_closed"
    OPEN = "open"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CallSite:
    call_site_id: str
    filename: str
    line: int
    column: int
    end_line: int
    end_column: int
    qualified_name: str
    receiver_expr: str
    method_name: str


@dataclass(frozen=True)
class OracleRecord:
    qualname: str
    impl_class: type | None
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    return_val: Any = None
    call_site: str = ""
    is_dispatch_target: bool = True
    caller_filename: str = ""
    caller_lineno: int = 0
    caller_column: int = -1
    caller_end_column: int = -1


@dataclass(frozen=True)
class ClosureVerdict:
    method_qualname: str
    is_closed: bool = False
    known_impls: list[type] = field(default_factory=list)
    open_signals: list[str] = field(default_factory=list)
    signal: str = "CLOSED"
    rationale: str = ""
    status: ClosureStatus | None = None
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        status = self.status
        if status is None:
            if self.is_closed:
                status = ClosureStatus.CLOSED
            else:
                try:
                    status = ClosureStatus(self.signal.lower())
                except ValueError:
                    status = ClosureStatus.OPEN
                if status is ClosureStatus.CLOSED:
                    status = ClosureStatus.OPEN
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "is_closed", status is ClosureStatus.CLOSED)
        if not self.reasons and self.rationale:
            object.__setattr__(self, "reasons", (self.rationale,))
        if not self.blockers and self.open_signals:
            object.__setattr__(self, "blockers", tuple(self.open_signals))


@dataclass(frozen=True)
class RewriteDecision:
    method_qualname: str
    allowed: bool
    status: ClosureStatus
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @classmethod
    def from_verdict(cls, verdict: ClosureVerdict) -> RewriteDecision:
        status = verdict.status or ClosureStatus.UNKNOWN
        allowed = status is ClosureStatus.CLOSED and not verdict.blockers
        reasons = verdict.reasons or verdict.evidence
        blockers = verdict.blockers
        if not allowed and not blockers:
            blockers = (f"closure status is {status.value}",)
        return cls(
            method_qualname=verdict.method_qualname,
            allowed=allowed,
            status=status,
            confidence=verdict.confidence,
            reasons=reasons,
            blockers=blockers,
            evidence=verdict.evidence,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "method_qualname": self.method_qualname,
            "allowed": self.allowed,
            "status": self.status.value,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class TransformPlan:
    target_node: cst.CSTNode | None
    replacement: cst.BaseExpression
    verdict: ClosureVerdict
    rationale: str = ""
    target_range: str | None = None
    target_call_site: CallSite | None = None
    strategy: str = "direct"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    temp_receiver: str = ""
    receiver_expr: str = ""
