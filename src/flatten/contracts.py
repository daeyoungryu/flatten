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
    reason_code: str = ""
    message: str = ""
    callsite_id: str = ""
    original_expression: str = ""
    planned_expression: str = ""
    observed_receiver_types: tuple[str, ...] = ()
    dispatch_order: tuple[str, ...] = ()
    closure_verdict: str = ""
    required_imports: tuple[str, ...] = ()
    safety_notes: tuple[str, ...] = ()
    proof_status: str = ""
    proof_reasons: tuple[str, ...] = ()
    proof_evidence: tuple[str, ...] = ()

    @classmethod
    def from_verdict(cls, verdict: ClosureVerdict) -> RewriteDecision:
        status = verdict.status or ClosureStatus.UNKNOWN
        allowed = status is ClosureStatus.CLOSED and not verdict.blockers
        reasons = verdict.reasons or verdict.evidence
        blockers = verdict.blockers
        if not allowed and not blockers:
            blockers = (f"closure status is {status.value}",)
        reason_code, message = _reason_code_for(status, allowed, blockers)
        return cls(
            method_qualname=verdict.method_qualname,
            allowed=allowed,
            status=status,
            confidence=verdict.confidence,
            reasons=reasons,
            blockers=blockers,
            evidence=verdict.evidence,
            reason_code=reason_code,
            message=message,
            closure_verdict=status.value,
            safety_notes=tuple(verdict.evidence),
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
            "reason_code": self.reason_code,
            "message": self.message,
            "callsite_id": self.callsite_id,
            "original_expression": self.original_expression,
            "planned_expression": self.planned_expression,
            "observed_receiver_types": list(self.observed_receiver_types),
            "dispatch_order": list(self.dispatch_order),
            "closure_verdict": self.closure_verdict or self.status.value,
            "required_imports": list(self.required_imports),
            "safety_notes": list(self.safety_notes),
            "proof_status": self.proof_status,
            "proof_reasons": list(self.proof_reasons),
            "proof_evidence": list(self.proof_evidence),
        }


def _reason_code_for(
    status: ClosureStatus,
    allowed: bool,
    blockers: tuple[str, ...],
) -> tuple[str, str]:
    if allowed:
        return "ALLOWED_CLOSED", "Rewrite is allowed by positive closure evidence."
    text = " ".join(blockers).lower()
    if "no observed impl" in text or "no observed receiver" in text:
        return (
            "UNSAFE_NO_RECEIVER_TYPES",
            "No observed receiver types are available for safe dispatch flattening.",
        )
    if "__getattr__" in text:
        return (
            "UNSAFE_DYNAMIC_GETATTR",
            "Dynamic getattr call cannot be safely flattened.",
        )
    if "__getattribute__" in text:
        return (
            "UNSAFE_DYNAMIC_GETATTRIBUTE",
            "__getattribute__ override can change method resolution.",
        )
    if "monkey patch" in text:
        return "UNSAFE_MONKEY_PATCH", "Runtime method replacement was detected."
    if "multiple inheritance" in text or "diamond" in text:
        return (
            "UNSAFE_MULTIPLE_INHERITANCE",
            "Multiple or diamond inheritance makes dispatch order unsafe to rewrite.",
        )
    if (
        "descriptor" in text
        or "property" in text
        or "staticmethod" in text
        or "classmethod" in text
    ):
        return (
            "UNSAFE_DESCRIPTOR_OR_BINDING",
            "Descriptor or binding semantics cannot be flattened safely.",
        )
    if "custom metaclass" in text:
        return "UNSAFE_CUSTOM_METACLASS", "Custom metaclass can alter dispatch semantics."
    if "super" in text:
        return "UNSAFE_SUPER_DEPENDENCY", "super() dependent method resolution is unsupported."
    if "async" in text or "generator" in text:
        return "UNSAFE_ASYNC_OR_GENERATOR", "Async or generator methods are unsupported."
    if "exception" in text:
        return "UNSAFE_EXCEPTION_BEHAVIOR", "Exception behavior may diverge after rewrite."
    if "side effect" in text:
        return (
            "UNSAFE_ARGUMENT_SIDE_EFFECTS",
            "Argument or receiver side effects may be reordered by rewrite.",
        )
    if (
        "unobserved" in text
        or "static class graph" in text
        or status in {ClosureStatus.OPEN, ClosureStatus.PROBABLY_CLOSED}
    ):
        return (
            "OPEN_CLOSURE_INCOMPLETE",
            "Closure is incomplete; unobserved implementations may exist.",
        )
    if status is ClosureStatus.UNKNOWN:
        return "UNKNOWN_UNSUPPORTED", "Closure status is unknown or unsupported."
    return "UNKNOWN_UNSUPPORTED", "Rewrite is unsupported by the current safety policy."


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
