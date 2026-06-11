import libcst as cst

from flatten.contracts import CallSite, ClosureStatus, ClosureVerdict, TransformPlan
from flatten.planner import RewritePlanner


def test_rewrite_planner_plan_preserves_all_transform_plan_fields():
    verdict = ClosureVerdict(
        "pkg.Shape.area",
        known_impls=[object],
        status=ClosureStatus.CLOSED,
        evidence=("typing.final method",),
    )
    site = CallSite(
        call_site_id="sample.py:10:4-10:12",
        filename="sample.py",
        line=10,
        column=4,
        end_line=10,
        end_column=12,
        qualified_name="s.area",
        receiver_expr="s",
        method_name="area",
    )
    original = TransformPlan(
        target_node=cst.Name("old"),
        replacement=cst.Name("new"),
        verdict=verdict,
        rationale="closed evidence",
        target_range="10:4-10:12",
        target_call_site=site,
        strategy="guarded_temp",
        confidence=0.87,
        risk_flags=["STATE_READ"],
        temp_receiver="_flatten_receiver_1",
        receiver_expr="factory()",
    )

    planned = RewritePlanner(opt_in=True).plan(verdict, [original])

    assert planned == [original]
    assert planned[0].strategy == "guarded_temp"
    assert planned[0].confidence == 0.87
    assert planned[0].temp_receiver == "_flatten_receiver_1"
    assert planned[0].receiver_expr == "factory()"
    assert planned[0].risk_flags == ["STATE_READ"]
    assert planned[0].target_call_site == site
