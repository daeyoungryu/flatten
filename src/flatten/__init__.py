"""flatten — polymorphic dispatch flattener via runtime tracing + LibCST."""

__version__ = "0.1.1"

from flatten.closure import ClosureChecker
from flatten.collapse import CollapseTransformer
from flatten.contracts import (
    CallSite,
    ClosureVerdict,
    OracleRecord,
    RewriteDecision,
    TransformPlan,
)
from flatten.discovery import discover_call_sites
from flatten.dispatch import DispatchTransformer
from flatten.harness import assert_equivalent
from flatten.observations import ObservationRecord
from flatten.planner import RewritePlanner
from flatten.report import AnalysisReport
from flatten.static import ClassHierarchy, ClassInfo, analyze_class_hierarchy
from flatten.tracer import Tracer, trace_calls

__all__ = [
    "Tracer",
    "trace_calls",
    "OracleRecord",
    "ObservationRecord",
    "CallSite",
    "discover_call_sites",
    "ClosureChecker",
    "ClosureVerdict",
    "RewriteDecision",
    "CollapseTransformer",
    "DispatchTransformer",
    "TransformPlan",
    "assert_equivalent",
    "RewritePlanner",
    "AnalysisReport",
    "ClassHierarchy",
    "ClassInfo",
    "analyze_class_hierarchy",
]
