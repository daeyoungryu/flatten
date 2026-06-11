import libcst as cst

from flatten.closure import ClosureChecker
from flatten.contracts import CallSite, ClosureStatus, ClosureVerdict
from flatten.planner import RewritePlanner


def test_rewrite_decision_has_structured_reason_code_for_no_receivers():
    verdict = ClosureVerdict(
        "pkg.Shape.area",
        known_impls=[],
        status=ClosureStatus.OPEN,
        blockers=("no observed impls",),
    )

    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert decision.allowed is False
    assert decision.reason_code == "UNSAFE_NO_RECEIVER_TYPES"
    assert "observed receiver" in decision.message


def test_rewrite_decision_maps_dynamic_getattr_to_reason_code():
    class Dynamic:
        def __getattr__(self, name):
            raise AttributeError(name)

        def run(self):
            return 1

    verdict = ClosureChecker().check("Dynamic.run", [Dynamic])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert verdict.status is ClosureStatus.UNSAFE
    assert decision.reason_code == "UNSAFE_DYNAMIC_GETATTR"


def test_rewrite_decision_maps_multiple_inheritance_to_reason_code():
    class Left:
        def run(self):
            return "left"

    class Right:
        def run(self):
            return "right"

    class Both(Left, Right):
        pass

    verdict = ClosureChecker().check("Left.run", [Both])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert verdict.status is ClosureStatus.UNSAFE
    assert decision.reason_code == "UNSAFE_MULTIPLE_INHERITANCE"


def test_rewrite_decision_json_includes_phase2_metadata_fields():
    verdict = ClosureVerdict(
        "pkg.Shape.area",
        known_impls=[object],
        status=ClosureStatus.CLOSED,
        evidence=("typing.final method",),
        confidence=0.93,
    )
    site = CallSite(
        call_site_id="sample.py:2:11-2:19",
        filename="sample.py",
        line=2,
        column=11,
        end_line=2,
        end_column=19,
        qualified_name="shape.area",
        receiver_expr="shape",
        method_name="area",
    )

    plan = RewritePlanner(opt_in=True).plan_from_observations(
        "def f(shape):\n    return shape.area()\n",
        [site],
        [],
        [verdict],
    )
    decision = RewritePlanner(opt_in=True).decision_for_plan(
        verdict,
        site,
        original_expression="shape.area()",
        planned_expression="Shape.area(shape)",
        observed_receiver_types=("pkg.Shape",),
        dispatch_order=("pkg.Shape",),
        required_imports=(),
        safety_notes=("typing.final method",),
    )

    payload = decision.to_json()

    assert plan == []
    assert payload["reason_code"] == "ALLOWED_CLOSED"
    assert payload["callsite_id"] == "sample.py:2:11-2:19"
    assert payload["original_expression"] == "shape.area()"
    assert payload["planned_expression"] == "Shape.area(shape)"
    assert payload["observed_receiver_types"] == ["pkg.Shape"]
    assert payload["dispatch_order"] == ["pkg.Shape"]
    assert payload["closure_verdict"] == "closed"
    assert payload["confidence"] == 0.93
    assert payload["required_imports"] == []
    assert payload["safety_notes"] == ["typing.final method"]


def test_reason_code_list_documented():
    cst.Module([])  # keep libcst imported in this test module for packaging smoke
    content = __import__("pathlib").Path("docs/REWRITE_POLICY.md").read_text(encoding="utf-8")
    for code in [
        "ALLOWED_CLOSED",
        "OPEN_CLOSURE_INCOMPLETE",
        "UNSAFE_NO_RECEIVER_TYPES",
        "UNSAFE_DYNAMIC_GETATTR",
        "UNSAFE_DYNAMIC_ATTRIBUTE_CALL",
        "UNSAFE_MONKEY_PATCH",
        "UNSAFE_MULTIPLE_INHERITANCE",
        "UNSAFE_UNRESOLVABLE_CLASS_REFERENCE",
        "UNSAFE_ALIAS_IMPORT",
        "UNSAFE_LOCAL_OR_NESTED_CLASS",
        "UNSAFE_DESCRIPTOR_OR_BINDING",
        "UNSAFE_CUSTOM_METACLASS",
        "UNSAFE_SUPER_DEPENDENCY",
        "UNSAFE_ARGUMENT_SIDE_EFFECTS",
        "UNSAFE_ASYNC_OR_GENERATOR",
        "UNSAFE_EXCEPTION_BEHAVIOR",
        "UNKNOWN_UNSUPPORTED",
    ]:
        assert code in content
