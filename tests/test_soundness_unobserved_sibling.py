import libcst as cst
from hypothesis import given
from hypothesis import strategies as st

from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import CallSite, ClosureStatus, TransformPlan
from flatten.planner import RewritePlanner


class Shape:
    def area(self):
        raise NotImplementedError


class Circle(Shape):
    def area(self):
        return 3.14


class Square(Shape):
    def area(self):
        return 4.0


class Triangle(Shape):
    def area(self):
        return 0.5


def test_unobserved_sibling_keeps_closure_open_and_blocks_rewrite_plan():
    verdict = ClosureChecker().check("Circle.area", [Circle, Square])

    assert verdict.method_qualname.endswith("Shape.area")
    assert verdict.status is not ClosureStatus.CLOSED
    assert not verdict.is_closed
    assert any("Triangle" in blocker for blocker in verdict.blockers)

    candidate = TransformPlan(
        target_node=None,
        replacement=cst.parse_expression("Circle.area(s)"),
        verdict=verdict,
        target_call_site=CallSite(
            call_site_id="sample.py:1:0-1:8",
            filename="sample.py",
            line=1,
            column=0,
            end_line=1,
            end_column=8,
            qualified_name="s.area",
            receiver_expr="s",
            method_name="area",
        ),
        strategy="guarded",
        confidence=0.95,
    )

    assert RewritePlanner(opt_in=True).plan(verdict, [candidate]) == []


@given(st.integers(min_value=1, max_value=4))
def test_static_unobserved_override_property_never_closes(extra_count):
    namespace: dict[str, object] = {}
    source_lines = [
        "class GeneratedBase:",
        "    def visit(self): return 'base'",
        "",
        "class ObservedA(GeneratedBase):",
        "    def visit(self): return 'observed-a'",
        "",
        "class ObservedB(GeneratedBase):",
        "    def visit(self): return 'observed-b'",
    ]
    known = {
        f"{__name__}.GeneratedBase",
        f"{__name__}.ObservedA",
        f"{__name__}.ObservedB",
    }
    subclasses = {
        f"{__name__}.GeneratedBase": {
            f"{__name__}.ObservedA",
            f"{__name__}.ObservedB",
        }
    }
    for index in range(extra_count):
        class_name = f"Hidden{index}"
        source_lines.extend(
            [
                "",
                f"class {class_name}(GeneratedBase):",
                f"    def visit(self): return 'hidden-{index}'",
            ]
        )
        known.add(f"{__name__}.{class_name}")
        subclasses[f"{__name__}.GeneratedBase"].add(f"{__name__}.{class_name}")

    exec("\n".join(source_lines), {"__name__": __name__}, namespace)
    observed_a = namespace["ObservedA"]
    observed_b = namespace["ObservedB"]
    assert isinstance(observed_a, type)
    assert isinstance(observed_b, type)

    verdict = ClosureChecker(
        ClosureConfig(
            static_known_classes=frozenset(known),
            static_subclasses=subclasses,
            use_runtime_subclasses_for_closure=False,
        )
    ).check("ObservedA.visit", [observed_a, observed_b])

    assert verdict.status is not ClosureStatus.CLOSED
    assert any("Hidden" in blocker for blocker in verdict.blockers)
