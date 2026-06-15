"""guarded_temp context coverage regression tests.

The transformer must hoist the receiver into a temp variable for ALL statement
contexts that support it (return, assign, expr_stmt), not only return.

Case A: return make().run()  → guarded_temp + hoisting (already works)
Case B: x = make().run()    → guarded_temp + hoisting (RED: temp used but never assigned)
Case C: make().run()        → guarded_temp + hoisting (RED: temp used but never assigned)
"""

import textwrap

from flatten.closure import ClosureChecker, ClosureConfig
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef
from flatten.planner import RewritePlanner
from flatten.transformer import rewrite_source_with_plan

SRC_RETURN = textwrap.dedent("""\
    from typing import final
    @final
    class A:
        def run(self): return "A"
    @final
    class B:
        def run(self): return "B"
    def make():
        return A()
    def entry():
        return make().run()
""")

SRC_ASSIGN = textwrap.dedent("""\
    from typing import final
    @final
    class A:
        def run(self): return "A"
    @final
    class B:
        def run(self): return "B"
    def make():
        return A()
    def entry():
        x = make().run()
        return x
""")

SRC_EXPR = textwrap.dedent("""\
    from typing import final
    _log = []
    @final
    class A:
        def run(self): _log.append("A")
    @final
    class B:
        def run(self): _log.append("B")
    def make():
        return A()
    def entry():
        make().run()
        return _log[:]
""")


def _plans_for(src: str) -> list:
    ns: dict = {}
    exec(compile(src, "<test>", "exec"), ns)  # noqa: S102
    A_cls, B_cls = ns["A"], ns["B"]
    sites = discover_call_sites(src, filename="<test>")
    run_site = next(s for s in sites if s.method_name == "run")
    checker = ClosureChecker(ClosureConfig(closed_world=True))
    verdict = checker.check("A.run", [A_cls, B_cls])

    def _obs(qualname: str, cls_name: str, order: int) -> ObservationRecord:
        return ObservationRecord(
            call_site_id=run_site.call_site_id,
            receiver_type=TypeRef(module="", qualname=cls_name, file=None, is_builtin=False),
            resolved_function=FunctionRef(
                module="", qualname=qualname, file=None, firstlineno=None
            ),
            method_name="run",
            frame_module="",
            order=order,
            qualname=qualname,
        )

    observations = [_obs("A.run", "A", 1), _obs("B.run", "B", 2)]
    planner = RewritePlanner(opt_in=True)
    return planner.plan_from_observations(src, sites, observations, [verdict])


def test_case_a_return_gets_guarded_temp() -> None:
    """return make().run() — guarded_temp with hoisting (already works)."""
    plans = _plans_for(SRC_RETURN)
    assert len(plans) == 1, f"Expected 1 plan, got {len(plans)}"
    assert plans[0].strategy == "guarded_temp", (
        f"Expected guarded_temp, got {plans[0].strategy!r}"
    )
    result = rewrite_source_with_plan(SRC_RETURN, plans)
    assert "_flatten_receiver_1 = make()" in result, (
        f"Temp-receiver hoisting missing from rewritten source:\n{result}"
    )


def test_case_b_assign_gets_guarded_temp() -> None:
    """x = make().run() — guarded_temp with hoisting (RED: assignment missing)."""
    plans = _plans_for(SRC_ASSIGN)
    assert len(plans) == 1, f"Expected 1 plan, got {len(plans)}"
    assert plans[0].strategy == "guarded_temp", (
        f"Expected guarded_temp, got {plans[0].strategy!r}"
    )
    result = rewrite_source_with_plan(SRC_ASSIGN, plans)
    assert "_flatten_receiver_1 = make()" in result, (
        f"Temp-receiver hoisting missing from assign context. "
        f"Rewritten source:\n{result}"
    )


def test_case_c_expr_stmt_gets_guarded_temp() -> None:
    """make().run() (expression statement) — guarded_temp with hoisting (RED)."""
    plans = _plans_for(SRC_EXPR)
    assert len(plans) == 1, f"Expected 1 plan, got {len(plans)}"
    assert plans[0].strategy == "guarded_temp", (
        f"Expected guarded_temp, got {plans[0].strategy!r}"
    )
    result = rewrite_source_with_plan(SRC_EXPR, plans)
    assert "_flatten_receiver_1 = make()" in result, (
        f"Temp-receiver hoisting missing from expr_stmt context. "
        f"Rewritten source:\n{result}"
    )
