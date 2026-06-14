"""flatten — polymorphic dispatch flattener via runtime tracing + LibCST."""

try:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("flatten-polymorph")
except Exception:
    __version__ = "unknown"

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
