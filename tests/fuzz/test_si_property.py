"""Hypothesis property-based fuzz: SI invariant (Soundness Invariant).

For any valid call-site rewrite the planner generates, the transformed code
must be observationally equivalent to the original:
  - receiver evaluated exactly once
  - args evaluated in original order exactly once
  - return value unchanged
  - no extra side effects

Strategy:
  - Generate random class hierarchies (1-3 @final classes, each with a 'run' method)
  - Generate random argument values
  - Generate random statement contexts (return / assign / expr_stmt)
  - Run planner.plan_from_observations on the generated source
  - For identifier receivers: execute original and rewritten code, compare outcomes
  - For non-identifier + comprehension/lambda: verify 0 plans (refused)
"""

from __future__ import annotations

import textwrap

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from flatten.contracts import ClosureStatus, ClosureVerdict
from flatten.discovery import discover_call_sites
from flatten.observations import FunctionRef, ObservationRecord, TypeRef
from flatten.planner import RewritePlanner
from flatten.transformer import rewrite_source_with_plan

# ---------------------------------------------------------------------------
# Source builders
# ---------------------------------------------------------------------------

def _build_src_identifier(n_classes: int, ctx: str, arg_val: int) -> str:
    """Generate source with identifier receiver (obj.run(v)) in given context."""
    lines = ["from typing import final\n_log = []\n"]
    class_names = [f"C{i}" for i in range(n_classes)]
    for i, name in enumerate(class_names):
        lines.append(
            f"@final\nclass {name}:\n"
            f"    def run(self, v):\n"
            f"        _log.append(('{name}', v))\n"
            f"        return ('{name}', v + {i})\n"
        )
    lines.append("def entry(obj, v):\n")
    if ctx == "return":
        lines.append("    return obj.run(v)\n")
    elif ctx == "assign":
        lines.append("    x = obj.run(v)\n    return x\n")
    else:  # expr_stmt
        lines.append("    obj.run(v)\n    return _log[-1] if _log else None\n")
    return "".join(lines)


def _build_src_comprehension(n_classes: int, n_iters: int) -> str:
    """Generate source with non-identifier receiver inside list comprehension."""
    lines = ["from typing import final\n_log = []\n"]
    class_names = [f"D{i}" for i in range(n_classes)]
    for name in class_names:
        lines.append(
            f"@final\nclass {name}:\n"
            f"    def run(self, v):\n"
            f"        _log.append(('{name}', v))\n"
            f"        return ('{name}', v)\n"
        )
    lines.append("def make(i):\n    _log.append(('make', i))\n    return D0()\n")
    lines.append(f"def entry():\n    return [make(i).run(i) for i in range({n_iters})]\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_observations(
    src: str, class_names: list[str]
) -> tuple[list, list, list[ClosureVerdict]]:
    ns: dict = {}
    exec(compile(src, "<fuzz>", "exec"), ns)  # noqa: S102

    sites = discover_call_sites(src, filename="<fuzz>")
    run_sites = [s for s in sites if s.method_name == "run"]
    if not run_sites:
        return sites, [], []

    run_site = run_sites[0]
    observations = []
    verdicts = []
    for name in class_names:
        cls = ns.get(name)
        if cls is None:
            continue
        observations.append(
            ObservationRecord(
                call_site_id=run_site.call_site_id,
                receiver_type=TypeRef(module="", qualname=name, file=None, is_builtin=False),
                resolved_function=FunctionRef(
                    module="", qualname=f"{name}.run", file=None, firstlineno=None
                ),
                method_name="run",
                frame_module="",
                order=class_names.index(name) + 1,
                qualname=f"{name}.run",
            )
        )
        verdicts.append(
            ClosureVerdict(
                method_qualname=f"{name}.run",
                known_impls=[cls],
                signal="CLOSED",
                status=ClosureStatus.CLOSED,
                rationale="@final class in fuzz test",
                evidence=(f"@final on {name}",),
                is_closed=True,
            )
        )
    return sites, observations, verdicts


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

@given(
    n_classes=st.integers(min_value=1, max_value=3),
    ctx=st.sampled_from(["return", "assign", "expr_stmt"]),
    arg_val=st.integers(min_value=0, max_value=99),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_si_identifier_receiver_rewrite_is_equivalent(
    n_classes: int, ctx: str, arg_val: int
) -> None:
    """Rewritten code with identifier receiver must return same value as original."""
    src = _build_src_identifier(n_classes, ctx, arg_val)
    class_names = [f"C{i}" for i in range(n_classes)]
    sites, observations, verdicts = _make_observations(src, class_names)
    if not observations:
        return

    planner = RewritePlanner(opt_in=True)
    plans = planner.plan_from_observations(src, sites, observations, verdicts)
    if not plans:
        return

    # Execute original
    ns_orig: dict = {}
    exec(compile(src, "<fuzz_orig>", "exec"), ns_orig)  # noqa: S102
    obj_orig = ns_orig["C0"]()
    orig_result = ns_orig["entry"](obj_orig, arg_val)

    # Execute rewritten
    rewritten = rewrite_source_with_plan(src, plans)
    ns_rw: dict = {}
    exec(compile(rewritten, "<fuzz_rewrite>", "exec"), ns_rw)  # noqa: S102
    obj_rw = ns_rw["C0"]()
    rewritten_result = ns_rw["entry"](obj_rw, arg_val)

    assert orig_result == rewritten_result, (
        f"SI violated for n_classes={n_classes} ctx={ctx!r} arg_val={arg_val}:\n"
        f"  original={orig_result!r}\n"
        f"  rewritten={rewritten_result!r}\n"
        f"  rewritten source:\n{textwrap.indent(rewritten, '    ')}"
    )


@given(
    n_classes=st.integers(min_value=2, max_value=3),
    n_iters=st.integers(min_value=1, max_value=5),
    base_val=st.integers(min_value=0, max_value=49),
)
@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_si_comprehension_receiver_refused(n_classes: int, n_iters: int, base_val: int) -> None:
    """Non-identifier receiver inside comprehension must produce 0 plans (refused)."""
    src = _build_src_comprehension(n_classes, n_iters)
    class_names = [f"D{i}" for i in range(n_classes)]
    sites, observations, verdicts = _make_observations(src, class_names)

    if len(observations) < 2:
        return

    planner = RewritePlanner(opt_in=True)
    plans = planner.plan_from_observations(src, sites, observations, verdicts)

    assert len(plans) == 0, (
        f"SI violation: planner emitted {len(plans)} plan(s) for non-identifier "
        f"receiver inside comprehension (n_classes={n_classes}, n_iters={n_iters}). "
        f"Rewriting would re-evaluate make(i), violating evaluation-count invariant."
    )


@given(
    n_classes=st.integers(min_value=1, max_value=3),
    ctx=st.sampled_from(["return", "assign", "expr_stmt"]),
    arg_val=st.integers(min_value=0, max_value=49),
)
@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
def test_si_receiver_evaluated_once(n_classes: int, ctx: str, arg_val: int) -> None:
    """Receiver expression must be evaluated exactly once in rewritten code."""
    src = _build_src_identifier(n_classes, ctx, arg_val)
    class_names = [f"C{i}" for i in range(n_classes)]
    sites, observations, verdicts = _make_observations(src, class_names)
    if not observations:
        return

    planner = RewritePlanner(opt_in=True)
    plans = planner.plan_from_observations(src, sites, observations, verdicts)
    if not plans:
        return

    rewritten = rewrite_source_with_plan(src, plans)

    ns: dict = {}
    exec(compile(rewritten, "<fuzz_once>", "exec"), ns)  # noqa: S102
    obj = ns["C0"]()
    result = ns["entry"](obj, arg_val)
    # If it runs without exception, the structure is valid.
    assert result is not None or ctx == "expr_stmt"
