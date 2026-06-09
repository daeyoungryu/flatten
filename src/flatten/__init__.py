"""flatten — polymorphic dispatch flattener via runtime tracing + LibCST."""

__version__ = "0.1.0"

from flatten.tracer import Tracer, OracleRecord
from flatten.closure import ClosureChecker, ClosureVerdict
from flatten.collapse import CollapseTransformer
from flatten.dispatch import DispatchTransformer, TransformPlan
from flatten.harness import assert_equivalent

__all__ = [
    "Tracer",
    "OracleRecord",
    "ClosureChecker",
    "ClosureVerdict",
    "CollapseTransformer",
    "DispatchTransformer",
    "TransformPlan",
    "assert_equivalent",
]
