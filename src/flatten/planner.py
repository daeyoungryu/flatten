"""Opt-in rewrite planning layer."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace

import libcst as cst

from flatten.collapse import collapse_source
from flatten.confidence import confidence_score
from flatten.contracts import CallSite, ClosureVerdict, RewriteDecision, TransformPlan
from flatten.observations import ObservationRecord, observation_type_name
from flatten.proofs import classify_rewrite_decision
from flatten.transformer import rewrite_source_with_plan

REWRITE_WARNING = (
    "# flatten: observed-based guess; unobserved implementations may exist"
)


class RewritePlanner:
    """Create and apply rewrite plans only when explicitly opted in."""

    def __init__(self, *, opt_in: bool = False) -> None:
        self.opt_in = opt_in

    def plan(
        self,
        verdict: ClosureVerdict,
        candidate_plans: Iterable[TransformPlan],
    ) -> list[TransformPlan]:
        decision = _with_proof(RewriteDecision.from_verdict(verdict))
        if not self.opt_in or not decision.allowed or decision.proof_status != "safe":
            return []
        return [
            replace(
                plan,
                rationale=plan.rationale
                or "observed-based guess; unobserved implementations may exist",
            )
            for plan in candidate_plans
        ]

    def decide(self, verdicts: Iterable[ClosureVerdict]) -> list[RewriteDecision]:
        return [_with_proof(RewriteDecision.from_verdict(verdict)) for verdict in verdicts]

    def decision_for_plan(
        self,
        verdict: ClosureVerdict,
        call_site: CallSite,
        *,
        original_expression: str,
        planned_expression: str,
        observed_receiver_types: tuple[str, ...],
        dispatch_order: tuple[str, ...],
        required_imports: tuple[str, ...] = (),
        safety_notes: tuple[str, ...] = (),
    ) -> RewriteDecision:
        base = _with_proof(RewriteDecision.from_verdict(verdict))
        return _with_proof(
            RewriteDecision(
                method_qualname=base.method_qualname,
                allowed=base.allowed,
                status=base.status,
                confidence=base.confidence,
                reasons=base.reasons,
                blockers=base.blockers,
                evidence=base.evidence,
                reason_code=base.reason_code,
                message=base.message,
                callsite_id=call_site.call_site_id,
                original_expression=original_expression,
                planned_expression=planned_expression,
                observed_receiver_types=observed_receiver_types,
                dispatch_order=dispatch_order,
                closure_verdict=base.status.value,
                required_imports=required_imports,
                safety_notes=safety_notes or base.safety_notes,
            )
        )

    def rewrite_source(self, source: str, plans: Iterable[TransformPlan]) -> str:
        if not self.opt_in:
            raise ValueError("rewrite is disabled by default; pass opt_in=True")
        plan_list = list(plans)
        if any(plan.target_call_site is not None for plan in plan_list):
            rewritten = rewrite_source_with_plan(source, plan_list)
        else:
            rewritten = collapse_source(source, plan_list)
        if rewritten.startswith(REWRITE_WARNING):
            return rewritten
        return f"{REWRITE_WARNING}\n{rewritten}"

    def plan_from_observations(
        self,
        source: str,
        call_sites: list[CallSite],
        observations: list[ObservationRecord],
        verdicts: list[ClosureVerdict],
    ) -> list[TransformPlan]:
        if not self.opt_in:
            return []
        decisions = {
            decision.method_qualname: decision for decision in self.decide(verdicts)
        }
        verdict = next(
            (
                item
                for item in verdicts
                if decisions[item.method_qualname].allowed
                and decisions[item.method_qualname].proof_status == "safe"
            ),
            None,
        )
        if verdict is None:
            return []

        observations_by_site: dict[str, list[ObservationRecord]] = defaultdict(list)
        for record in observations:
            observations_by_site[record.call_site_id].append(record)

        plans: list[TransformPlan] = []
        for site in call_sites:
            site_observations = observations_by_site.get(site.call_site_id, [])
            if not site_observations:
                continue
            receiver_types = _ordered_receiver_types(
                {observation_type_name(record) for record in site_observations},
                verdict,
            )
            if not receiver_types:
                continue
            strategy = "direct" if len(receiver_types) == 1 else "guarded"
            temp_receiver = ""
            receiver_expr = ""
            receiver_override = None
            if len(receiver_types) > 1 and not site.receiver_expr.isidentifier():
                strategy = "guarded_temp"
                temp_receiver = f"_flatten_receiver_{len(plans) + 1}"
                receiver_expr = site.receiver_expr
                receiver_override = temp_receiver
            replacement = _replacement_for_site(
                source,
                site,
                receiver_types,
                receiver_override=receiver_override,
            )
            score = confidence_score(verdict)
            plans.append(
                TransformPlan(
                    target_node=None,
                    replacement=replacement,
                    verdict=verdict,
                    rationale=verdict.rationale,
                    target_range=f"{site.line}:{site.column}-{site.end_line}:{site.end_column}",
                    target_call_site=site,
                    strategy=strategy,
                    confidence=score,
                    risk_flags=list(verdict.open_signals),
                    temp_receiver=temp_receiver,
                    receiver_expr=receiver_expr,
                )
            )
        return plans


def _with_proof(decision: RewriteDecision) -> RewriteDecision:
    proof = classify_rewrite_decision(decision)
    return replace(
        decision,
        proof_status=proof.status.value,
        proof_reasons=proof.reasons,
        proof_evidence=proof.evidence,
    )


def _replacement_for_site(
    source: str,
    site: CallSite,
    receiver_types: list[str],
    *,
    receiver_override: str | None = None,
) -> cst.BaseExpression:
    original = _call_at_site(source, site)
    receiver = receiver_override or site.receiver_expr
    args = [receiver] + [cst.Module([]).code_for_node(arg) for arg in original.args]
    calls = [
        f"{receiver_type.rsplit('.', 1)[-1]}.{site.method_name}({', '.join(args)})"
        for receiver_type in receiver_types
    ]
    if len(calls) == 1:
        return cst.parse_expression(calls[0])
    if receiver_override is None:
        expr = cst.Module([]).code_for_node(original)
    else:
        expr = f"{receiver}.{site.method_name}({', '.join(args[1:])})"
    for receiver_type, call in reversed(list(zip(receiver_types, calls, strict=True))):
        class_name = receiver_type.rsplit(".", 1)[-1]
        expr = f"{call} if isinstance({receiver}, {class_name}) else {expr}"
    return cst.parse_expression(expr)


def _ordered_receiver_types(receiver_types: set[str], verdict: ClosureVerdict) -> list[str]:
    impls = [impl for impl in verdict.known_impls if isinstance(impl, type)]
    if not impls:
        return sorted(receiver_types)
    by_name: dict[str, type] = {}
    for impl in impls:
        by_name[impl.__qualname__] = impl
        by_name[impl.__name__] = impl
        by_name[f"{impl.__module__}.{impl.__qualname__}"] = impl
    resolved: list[tuple[str, type]] = []
    unresolved: list[str] = []
    for name in receiver_types:
        cls = by_name.get(name) or by_name.get(name.rsplit(".", 1)[-1])
        if cls is None:
            unresolved.append(name)
        else:
            resolved.append((name, cls))
    if unresolved:
        return []
    return [
        name
        for name, _ in sorted(
            resolved,
            key=lambda item: (-len(item[1].__mro__), item[1].__module__, item[1].__qualname__),
        )
    ]


def _call_at_site(source: str, site: CallSite) -> cst.Call:
    from flatten.discovery import discover_call_sites

    module = cst.parse_module(source)
    found: list[cst.Call] = []

    class Finder(cst.CSTVisitor):
        METADATA_DEPENDENCIES = ()

        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute):
                found.append(node)

    module.visit(Finder())
    sites = discover_call_sites(source, filename=site.filename)
    for candidate, candidate_site in zip(found, sites, strict=True):
        same_id = candidate_site.call_site_id == site.call_site_id
        same_position = (
            candidate_site.line == site.line
            and candidate_site.column == site.column
            and candidate_site.end_line == site.end_line
            and candidate_site.end_column == site.end_column
        )
        if same_id or same_position:
            return candidate
    raise ValueError(f"call site not found: {site.call_site_id}")
