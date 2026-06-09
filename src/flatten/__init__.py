"""flatten — polymorphic dispatch flattener via runtime tracing + LibCST."""

__version__ = "0.1.0"

from flatten.contracts import ClosureVerdict, OracleRecord, TransformPlan
from flatten.tracer import Tracer, trace_calls
from flatten.closure import ClosureChecker
from flatten.collapse import CollapseTransformer
from flatten.dispatch import DispatchTransformer
from flatten.harness import assert_equivalent

__all__ = [
    "Tracer",
    "trace_calls",
    "OracleRecord",
    "ClosureChecker",
    "ClosureVerdict",
    "CollapseTransformer",
    "DispatchTransformer",
    "TransformPlan",
    "assert_equivalent",
]
