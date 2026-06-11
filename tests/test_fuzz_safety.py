from hypothesis import given, settings
from hypothesis import strategies as st

from flatten.closure import ClosureChecker
from flatten.contracts import ClosureStatus
from flatten.planner import RewritePlanner


@settings(max_examples=75)
@given(
    method_name=st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True),
    hidden_count=st.integers(min_value=0, max_value=3),
    observed_count=st.integers(min_value=1, max_value=3),
)
def test_fuzz_safety_rejects_or_closes_without_crashing(method_name, hidden_count, observed_count):
    namespace: dict[str, object] = {}
    lines = [
        "class Base:",
        f"    def {method_name}(self): return 'base'",
    ]
    for index in range(observed_count):
        lines.extend(
            [
                "",
                f"class Observed{index}(Base):",
                f"    def {method_name}(self): return 'observed-{index}'",
            ]
        )
    for index in range(hidden_count):
        lines.extend(
            [
                "",
                f"class Hidden{index}(Base):",
                f"    def {method_name}(self): return 'hidden-{index}'",
            ]
        )
    exec("\n".join(lines), namespace)
    observed = [namespace[f"Observed{index}"] for index in range(observed_count)]
    assert all(isinstance(item, type) for item in observed)

    verdict = ClosureChecker().check(f"Base.{method_name}", observed)
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert verdict.status in {
        ClosureStatus.CLOSED,
        ClosureStatus.OPEN,
        ClosureStatus.PROBABLY_CLOSED,
        ClosureStatus.UNSAFE,
        ClosureStatus.UNKNOWN,
    }
    if hidden_count:
        assert decision.allowed is False
