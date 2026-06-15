"""SI regression: non-identifier receiver with side effects must not be re-evaluated.

Invariant: when planner emits a plan, evaluation count of every sub-expression must
be identical to the original. A comprehension context with a non-identifier receiver
(nxt(i)) and ≥2 implementations cannot be safely rewritten — REFUSE is required.
"""

import textwrap

from flatten.closure import ClosureChecker, ClosureConfig
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef
from flatten.planner import RewritePlanner

SRC = textwrap.dedent("""\
    from typing import final
    _log = []
    @final
    class A:
        def run(self, x): return ("A", x)
    @final
    class B:
        def run(self, x): return ("B", x)
    def nxt(i):
        _log.append(i)
        return A() if len(_log) % 2 == 1 else B()
    def main():
        _log.clear()
        results = [nxt(i).run(i) for i in range(4)]
        return {"results": results, "calls": len(_log)}
""")


def _exec_classes(src: str) -> tuple[type, type]:
    ns: dict = {}
    exec(compile(src, "<test>", "exec"), ns)  # noqa: S102
    return ns["A"], ns["B"]


def test_si_receiver_multi_eval_refused() -> None:
    """Non-identifier receiver with ≥2 impls inside list comprehension → 0 plans.

    The receiver nxt(i) has side effects. A guarded rewrite would evaluate it
    multiple times, violating the SI evaluation-count invariant.
    """
    A_cls, B_cls = _exec_classes(SRC)
    sites = discover_call_sites(SRC, filename="<test>")
    run_site = next(s for s in sites if s.method_name == "run")

    assert not run_site.receiver_expr.isidentifier(), (
        f"Precondition: receiver '{run_site.receiver_expr}' should be non-identifier"
    )

    checker = ClosureChecker(ClosureConfig(closed_world=True))
    verdict_a = checker.check("A.run", [A_cls, B_cls])
    verdict_b = checker.check("B.run", [A_cls, B_cls])

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
    plans = planner.plan_from_observations(
        SRC, sites, observations, [verdict_a, verdict_b]
    )

    assert len(plans) == 0, (
        f"Expected 0 plans — receiver re-evaluation would violate SI. "
        f"Got {len(plans)} plan(s) with strategies: {[p.strategy for p in plans]}"
    )
