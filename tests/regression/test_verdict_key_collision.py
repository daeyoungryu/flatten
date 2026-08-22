"""Verdict key collision: contradictory verdicts for the same method_qualname.

When two ClosureVerdict objects share the same method_qualname but disagree on
status (CLOSED vs OPEN), the planner must apply the conservative (less permissive)
verdict regardless of input order.

Current bug: plan_from_observations uses dict comprehension (last-wins), so
[verdict_open, verdict_closed] incorrectly produces 1 plan.
"""

from __future__ import annotations

from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef
from flatten.planner import RewritePlanner

SRC = """\
from typing import final
@final
class A:
    def run(self): return 'A'
@final
class B:
    def run(self): return 'B'
def make():
    return A()
def entry():
    x = make().run()
    return x
"""


def _setup() -> tuple[type, type, list, list]:
    ns: dict = {}
    exec(compile(SRC, "<test>", "exec"), ns)  # noqa: S102
    A_cls, B_cls = ns["A"], ns["B"]
    sites = discover_call_sites(SRC, filename="<test>")
    run_site = next(s for s in sites if s.method_name == "run")
    obs = [
        ObservationRecord(
            call_site_id=run_site.call_site_id,
            receiver_type=TypeRef(module="", qualname="A", file=None, is_builtin=False),
            resolved_function=FunctionRef(
                module="", qualname="A.run", file=None, firstlineno=None
            ),
            method_name="run",
            frame_module="",
            order=1,
            qualname="A.run",
        ),
    ]
    return A_cls, B_cls, sites, obs


def test_collision_open_then_closed_gives_zero_plans() -> None:
    """[verdict_open, verdict_closed] → 0 plans (conservative open wins).

    With last-wins bug: closed dict entry overwrites open → 1 plan emitted.
    Expected behavior: open status is more conservative → 0 plans.
    """
    A_cls, B_cls, sites, obs = _setup()

    verdict_open = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[A_cls, B_cls],
        open_signals=["unobserved subclass"],
        signal="OPEN",
        status=ClosureStatus.OPEN,
        rationale="unobserved subclass",
        blockers=("unobserved subclass",),
        is_closed=False,
    )
    verdict_closed = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[A_cls, B_cls],
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        rationale="typing.final class",
        evidence=("checked final",),
        is_closed=True,
    )

    planner = RewritePlanner(opt_in=True)
    plans = planner.plan_from_observations(
        SRC, sites, obs, [verdict_open, verdict_closed]
    )
    assert len(plans) == 0, (
        f"Expected 0 plans when OPEN verdict conflicts with CLOSED for same method. "
        f"Got {len(plans)} plan(s). Conservative verdict (OPEN) must win regardless of order."
    )


def test_collision_closed_then_open_gives_zero_plans() -> None:
    """[verdict_closed, verdict_open] → 0 plans (conservative open wins).

    This ordering already works with the current last-wins implementation,
    but is included to ensure both orderings are verified together.
    """
    A_cls, B_cls, sites, obs = _setup()

    verdict_closed = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[A_cls, B_cls],
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        rationale="typing.final class",
        evidence=("checked final",),
        is_closed=True,
    )
    verdict_open = ClosureVerdict(
        method_qualname="A.run",
        known_impls=[A_cls, B_cls],
        open_signals=["unobserved subclass"],
        signal="OPEN",
        status=ClosureStatus.OPEN,
        rationale="unobserved subclass",
        blockers=("unobserved subclass",),
        is_closed=False,
    )

    planner = RewritePlanner(opt_in=True)
    plans = planner.plan_from_observations(
        SRC, sites, obs, [verdict_closed, verdict_open]
    )
    assert len(plans) == 0, (
        f"Expected 0 plans when CLOSED verdict conflicts with OPEN for same method. "
        f"Got {len(plans)} plan(s)."
    )
