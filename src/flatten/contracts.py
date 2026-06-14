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
    """A discovered method call site in a Python source file.

    Attributes:
        call_site_id: Unique identifier string (e.g. ``file.py:10:4-10:18``).
        filename: Source file path (normalized, forward-slash).
        line: 1-based start line of the call expression.
        column: 0-based start column.
        end_line: 1-based end line of the call expression.
        end_column: 0-based end column.
        qualified_name: Dotted method name (e.g. ``MyClass.method``).
        receiver_expr: Source text of the receiver (e.g. ``obj`` or ``make()``).
        method_name: Unqualified method name (e.g. ``method``).
    """

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
    """A recorded function call captured during runtime tracing.

    Attributes:
        qualname: Qualified name of the observed function (e.g. ``MyClass.method``).
        impl_class: Concrete receiver class, or None for non-method calls.
        args: Positional argument snapshots at call time.
        kwargs: Keyword argument snapshots at call time.
        return_val: Return value snapshot (captured if ``capture_values=True``).
        call_site: Source location string ``file:lineno``.
        is_dispatch_target: True when the receiver had ``self``/``cls`` as first arg.
        caller_filename: Resolved path of the caller's source file.
        caller_lineno: Line number in the caller's source.
        caller_column: Column offset of the call expression.
        caller_end_column: End column of the call expression.
        receiver_var_name: Variable name of the receiver for same-line disambiguation.
    """

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
    receiver_var_name: str = ""


@dataclass
class ClosureVerdict:
    """Verdict on whether a method's dispatch is closed (safe to flatten).

    Attributes:
        method_qualname: Qualified method name (e.g. ``Base.method``).
        is_closed: True if the dispatch is provably closed.
        known_impls: Concrete implementation classes observed or inferred.
        open_signals: Human-readable reasons the closure is open/unsafe.
        signal: One of ``CLOSED``, ``OPEN``, ``UNSAFE``, ``UNKNOWN``.
        rationale: Human-readable explanation of the verdict.
        status: Strongly-typed ``ClosureStatus`` (computed in ``__post_init__``).
        confidence: Float [0, 1] confidence score.
        reasons: Reasons supporting the verdict (from evidence or rationale).
        blockers: Reasons preventing rewrite authorization.
        evidence: Positive evidence strings that support a safe rewrite.
    """

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
        self.status = status
        self.is_closed = status is ClosureStatus.CLOSED
        if not self.reasons and self.rationale:
            self.reasons = (self.rationale,)
        if not self.blockers and self.open_signals:
            self.blockers = tuple(self.open_signals)


@dataclass(frozen=True)
class RewriteDecision:
    """Authorization decision for rewriting a specific method dispatch.

    Attributes:
        method_qualname: Qualified method name this decision applies to.
        allowed: True if the rewrite is authorized.
        status: Closure status that drove this decision.
        confidence: Float [0, 1] confidence in the decision.
        reasons: Positive reasons supporting authorization.
        blockers: Reasons preventing authorization.
        evidence: Evidence strings from the underlying ClosureVerdict.
        reason_code: Machine-readable code (e.g. ``ALLOWED_CLOSED``).
        message: Human-readable explanation of the decision.
        callsite_id: Target call site identifier when decision is site-specific.
        original_expression: Source text of the original call expression.
        planned_expression: Source text of the replacement expression.
        observed_receiver_types: Concrete receiver type names observed at runtime.
        dispatch_order: Ordered receiver type names for the guard chain.
        closure_verdict: String copy of the closure status value.
        required_imports: Import statements needed by the replacement expression.
        safety_notes: Additional notes about rewrite safety.
        proof_status: Status string from formal proof classification.
        proof_reasons: Reasons from the proof classification.
        proof_evidence: Evidence from the proof classification.
        proof_artifact: Optional structured artifact from proof analysis.
    """

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
    proof_artifact: dict[str, Any] | None = None

    @classmethod
    def from_verdict(cls, verdict: ClosureVerdict) -> RewriteDecision:
        status = verdict.status or ClosureStatus.UNKNOWN
        allowed = (
            status is ClosureStatus.CLOSED
            and not verdict.blockers
            and bool(verdict.evidence)
        )
        reasons = verdict.reasons or verdict.evidence
        blockers = verdict.blockers
        if status is ClosureStatus.CLOSED and not verdict.evidence:
            blockers = (*blockers, "missing rewrite evidence")
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
            "proof_artifact": self.proof_artifact,
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
