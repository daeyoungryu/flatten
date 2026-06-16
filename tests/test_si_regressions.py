"""SI regression tests: 7 RED (before fixes) + 1 META (always GREEN).

Gate is law: only fix src/flatten/ source code to make these GREEN.
Never decorate tests with skip or xfail markers in this file.
Invariants tested:
  RP  Receiver Pinning  — direct unguarded static call must not be emitted for unpinned receivers
  SE  Single Evaluation — guarded_temp must not be emitted in unhoistable contexts
  P2  Tracer records    — only dispatch records stored; outcome field distinguishes raise vs return
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import final

from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef
from flatten.planner import RewritePlanner
from flatten.tracer import Tracer
from flatten.transformer import rewrite_source_with_plan

# ---------------------------------------------------------------------------
# META — always GREEN
# ---------------------------------------------------------------------------

_EXPECTED_TEST_NAMES = [
    "test_P0_unpinned_receiver_rewrite_is_guarded_or_refused",
    "test_P0_direct_rewrite_preserves_behavior_for_unobserved_receiver",
    "test_P1_guarded_temp_if_condition_is_refused",
    "test_P1_guarded_temp_while_condition_is_refused",
    "test_P1_guarded_temp_assert_stmt_is_refused",
    "test_P2_tracer_retains_only_dispatch_records",
    "test_P2_exception_outcome_is_distinguishable_from_return_none",
]


def test_META_gate_is_intact() -> None:
    """Verify the gate file is untampered: no xfail/skip decorators, all 7 RED tests present."""
    source = Path(__file__).read_text(encoding="utf-8")
    for name in _EXPECTED_TEST_NAMES:
        assert name in source, f"Required test {name!r} missing from gate file"
    # Build forbidden patterns via concatenation so the literal strings don't appear
    # in THIS source file and trigger false positives from the check itself.
    _skip_deco = "\n@" + "pytest.mark.skip"
    _xfail_deco = "\n@" + "pytest.mark.xfail"
    _skip_call = "pytest" + ".skip("
    _xfail_call = "pytest" + ".xfail("
    assert _skip_deco not in source, "Gate file must not use skip decorator"
    assert _xfail_deco not in source, "Gate file must not use xfail decorator"
    assert _skip_call not in source, "Gate file must not call pytest.skip"
    assert _xfail_call not in source, "Gate file must not call pytest.xfail"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _closed_verdict(qualname: str, impls: list[type], label: str) -> ClosureVerdict:
    return ClosureVerdict(
        method_qualname=qualname,
        known_impls=impls,
        signal="CLOSED",
        status=ClosureStatus.CLOSED,
        rationale="regression test fixture",
        evidence=(f"@final on {label}",),
        is_closed=True,
    )


def _obs(site_id: str, cls: type, qualname: str, method: str) -> ObservationRecord:
    return ObservationRecord(
        call_site_id=site_id,
        receiver_type=TypeRef(module="", qualname=cls.__name__, file=None, is_builtin=False),
        resolved_function=FunctionRef(module="", qualname=qualname, file=None, firstlineno=None),
        method_name=method,
        frame_module="",
        order=1,
        qualname=qualname,
    )


# ---------------------------------------------------------------------------
# P0 / RP  Receiver Pinning
# ---------------------------------------------------------------------------

_SRC_P0 = textwrap.dedent("""\
    from typing import final

    @final
    class Worker:
        def run(self, v):
            return ("Worker", v + 1)

    class DuckWorker:
        def run(self, v):
            return ("Duck", v + 1)

    def entry(obj, v):
        return obj.run(v)
""")


def _p0_plans() -> list:
    """Plans for _SRC_P0 with Worker as the sole observed implementation."""
    ns: dict = {}
    exec(compile(_SRC_P0, "<p0>", "exec"), ns)  # noqa: S102
    Worker = ns["Worker"]
    sites = discover_call_sites(_SRC_P0, filename="<p0>")
    run_sites = [s for s in sites if s.method_name == "run"]
    assert run_sites, "expected to discover obj.run() call site"
    site = run_sites[0]
    planner = RewritePlanner(opt_in=True)
    return planner.plan_from_observations(
        _SRC_P0,
        sites,
        [_obs(site.call_site_id, Worker, "Worker.run", "run")],
        [_closed_verdict("Worker.run", [Worker], "Worker")],
    )


def test_P0_unpinned_receiver_rewrite_is_guarded_or_refused() -> None:
    """Identifier receiver + 1 impl must not produce 'direct' (unguarded static call).

    'direct' emits Worker.run(obj, v), which bypasses dynamic dispatch.  Any
    subclass or duck-compatible object passed at runtime silently uses Worker's
    implementation, violating Receiver Pinning.  The planner must refuse or use
    'guarded' (isinstance check) instead.
    """
    for plan in _p0_plans():
        assert plan.strategy != "direct", (
            f"P0/RP: identifier receiver with 1 observed impl must not produce "
            f"'direct' strategy.  Got strategy={plan.strategy!r}.  "
            f"'direct' pins the receiver type unsoundly."
        )


def test_P0_direct_rewrite_preserves_behavior_for_unobserved_receiver() -> None:
    """Rewritten code must preserve behaviour when an unobserved type is passed.

    We observe only Worker at the call site.  A 'direct' rewrite emits
    Worker.run(obj, v), returning ('Worker', ...) even when obj is a DuckWorker.
    That is a silent correctness bug (SI violation).
    """
    plans = _p0_plans()
    if not plans:
        return  # refused — SI preserved, test passes

    rewritten = rewrite_source_with_plan(_SRC_P0, plans)
    ns: dict = {}
    exec(compile(rewritten, "<p0_rw>", "exec"), ns)  # noqa: S102
    duck = ns["DuckWorker"]()

    result = ns["entry"](duck, 5)
    assert result == ("Duck", 6), (
        f"P0/RP: rewritten code returned {result!r} for DuckWorker argument instead "
        f"of ('Duck', 6).  Direct static binding violated receiver pinning."
    )


# ---------------------------------------------------------------------------
# P1 / SE  Single Evaluation in unhoistable contexts
# ---------------------------------------------------------------------------

_SRC_P1_IF = textwrap.dedent("""\
    from typing import final

    @final
    class A:
        def run(self):
            return True

    @final
    class B:
        def run(self):
            return False

    def make():
        return A()

    def entry():
        if make().run():
            return "yes"
        return "no"
""")

_SRC_P1_WHILE = textwrap.dedent("""\
    from typing import final

    @final
    class A:
        def run(self):
            return False

    @final
    class B:
        def run(self):
            return False

    def make():
        return A()

    def entry():
        while make().run():
            break
        return "done"
""")

_SRC_P1_ASSERT = textwrap.dedent("""\
    from typing import final

    @final
    class A:
        def run(self):
            return True

    @final
    class B:
        def run(self):
            return True

    def make():
        return A()

    def entry():
        assert make().run()
        return "ok"
""")


def _p1_plans(src: str) -> list:
    """Plans for src with non-identifier receiver and 2 final impls."""
    ns: dict = {}
    exec(compile(src, "<p1>", "exec"), ns)  # noqa: S102
    A_cls, B_cls = ns["A"], ns["B"]
    sites = discover_call_sites(src, filename="<p1>")
    run_sites = [s for s in sites if s.method_name == "run"]
    assert run_sites, "expected to discover .run() call site"
    site = run_sites[0]
    verdicts = [
        _closed_verdict("A.run", [A_cls, B_cls], "A"),
        _closed_verdict("B.run", [A_cls, B_cls], "B"),
    ]
    observations = [
        _obs(site.call_site_id, A_cls, "A.run", "run"),
        _obs(site.call_site_id, B_cls, "B.run", "run"),
    ]
    return RewritePlanner(opt_in=True).plan_from_observations(src, sites, observations, verdicts)


def test_P1_guarded_temp_if_condition_is_refused() -> None:
    """Non-identifier receiver in 'if' condition must produce 0 plans.

    guarded_temp hoisting requires inserting '_t = make()' before the statement.
    The transformer's leave_SimpleStatementLine cannot reach into compound-statement
    conditions (If.test).  Emitting a plan here produces NameError at runtime.
    """
    plans = _p1_plans(_SRC_P1_IF)
    assert len(plans) == 0, (
        f"P1/SE: non-identifier receiver inside 'if' condition must be refused "
        f"(transformer cannot hoist temp into compound-statement condition).  "
        f"Got {len(plans)} plan(s) with strategies {[p.strategy for p in plans]}."
    )


def test_P1_guarded_temp_while_condition_is_refused() -> None:
    """Non-identifier receiver in 'while' condition must produce 0 plans.

    Same hoist-impossibility as 'if' condition.  A temp assignment before the
    loop only covers the first iteration; subsequent iterations re-evaluate the
    guard without a temp, producing broken or undefined behaviour.
    """
    plans = _p1_plans(_SRC_P1_WHILE)
    assert len(plans) == 0, (
        f"P1/SE: non-identifier receiver inside 'while' condition must be refused "
        f"(transformer cannot hoist temp into loop guard).  "
        f"Got {len(plans)} plan(s) with strategies {[p.strategy for p in plans]}."
    )


def test_P1_guarded_temp_assert_stmt_is_refused() -> None:
    """Non-identifier receiver in 'assert' statement must produce 0 plans.

    leave_SimpleStatementLine only handles Return / Assign / AnnAssign / Expr.
    cst.Assert is absent from that list, so the temp assignment is never emitted
    and the rewritten code contains an undefined name.
    """
    plans = _p1_plans(_SRC_P1_ASSERT)
    assert len(plans) == 0, (
        f"P1/SE: non-identifier receiver inside 'assert' statement must be refused "
        f"(transformer cannot hoist temp before assert).  "
        f"Got {len(plans)} plan(s) with strategies {[p.strategy for p in plans]}."
    )


# ---------------------------------------------------------------------------
# P2  Tracer correctness
# ---------------------------------------------------------------------------

def test_P2_tracer_retains_only_dispatch_records() -> None:
    """Tracer must expose a dispatch_records view containing only method-call records.

    tracer.records accumulates ALL call records (including plain functions).  The
    dispatch_records property must return a filtered view that excludes non-dispatch
    records (is_dispatch_target=False), giving callers a clean separation between
    method-dispatch observations and other instrumented calls.

    This test is RED before the fix because Tracer has no dispatch_records attribute.
    """

    def _add(x: int) -> int:  # non-method: is_dispatch_target=False
        return x + 1

    def _mul(x: int) -> int:  # non-method: is_dispatch_target=False
        return x * 2

    @final
    class _Dispatcher:
        def run(self, x: int) -> int:  # method: is_dispatch_target=True
            return x

    with Tracer() as tracer:
        for i in range(20):
            _add(i)
            _mul(i)
        _Dispatcher().run(99)

    # This raises AttributeError until Tracer gains the dispatch_records property.
    dispatch = tracer.dispatch_records  # type: ignore[attr-defined]

    assert all(r.is_dispatch_target for r in dispatch), (
        f"P2: dispatch_records returned non-dispatch record(s): "
        f"{[r.qualname for r in dispatch if not r.is_dispatch_target]}"
    )
    assert not any("_add" in r.qualname or "_mul" in r.qualname for r in dispatch), (
        f"P2: dispatch_records must exclude plain-function calls (_add, _mul). "
        f"Got: {[r.qualname for r in dispatch]}"
    )
    assert any("_Dispatcher" in r.qualname for r in dispatch), (
        "P2: dispatch_records must include _Dispatcher.run method call"
    )


def test_P2_exception_outcome_is_distinguishable_from_return_none() -> None:
    """OracleRecord must carry an 'outcome' field: 'return' or 'raise'.

    Currently _flush_pending_as_exception stores return_val=None, which is
    indistinguishable from a method that legitimately returns None.  The
    'outcome' field lets callers distinguish normal returns from exceptions.
    """

    @final
    class _Raiser:
        def run(self) -> None:
            raise ValueError("intentional")

    @final
    class _NoneReturner:
        def run(self) -> None:
            return None

    with Tracer() as tracer:
        try:
            _Raiser().run()
        except ValueError:
            pass
        _NoneReturner().run()

    dispatch = [r for r in tracer.records if r.is_dispatch_target]
    raiser_recs = [r for r in dispatch if "Raiser" in r.qualname]
    none_recs = [r for r in dispatch if "NoneReturner" in r.qualname]

    assert raiser_recs, "Raiser.run not found in tracer dispatch records"
    assert none_recs, "NoneReturner.run not found in tracer dispatch records"

    raiser_rec = raiser_recs[0]
    none_rec = none_recs[0]

    assert raiser_rec.outcome == "raise", (
        f"P2: _Raiser.run raised ValueError but record.outcome="
        f"{raiser_rec.outcome!r}.  Expected 'raise'."
    )
    assert none_rec.outcome == "return", (
        f"P2: _NoneReturner.run returned None but record.outcome="
        f"{none_rec.outcome!r}.  Expected 'return'."
    )
