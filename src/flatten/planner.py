"""Opt-in rewrite planning layer."""

from __future__ import annotations

import functools
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace

import libcst as cst

from flatten.collapse import collapse_source
from flatten.confidence import confidence_score
from flatten.contracts import (
    CallSite,
    ClosureStatus,
    ClosureVerdict,
    RewriteDecision,
    TransformPlan,
)
from flatten.observations import ObservationRecord, observation_type_name
from flatten.proofs import classify_rewrite_decision
from flatten.transformer import rewrite_source_with_plan

# Conservatism order for verdict collision resolution (lower = more conservative).
_CONSERVATISM_RANK: dict[ClosureStatus, int] = {
    ClosureStatus.UNSAFE: 0,
    ClosureStatus.OPEN: 1,
    ClosureStatus.UNKNOWN: 2,
    ClosureStatus.PROBABLY_CLOSED: 3,
    ClosureStatus.CLOSED: 4,
}


def _most_conservative(a: ClosureVerdict, b: ClosureVerdict) -> ClosureVerdict:
    """Return the more conservative of two verdicts for the same method_qualname."""
    a_rank = _CONSERVATISM_RANK.get(a.status) if a.status is not None else 2
    b_rank = _CONSERVATISM_RANK.get(b.status) if b.status is not None else 2
    a_rank = a_rank if a_rank is not None else 2
    b_rank = b_rank if b_rank is not None else 2
    return a if a_rank <= b_rank else b


class EvaluationSafety:
    """Determines safe rewrite strategy for a call site, enforcing the SI invariant.

    Strategy selection table:
    | receiver         | impls | context                         | strategy     |
    |-----------------|-------|---------------------------------|-------------|
    | pure identifier | 1     | any                             | REFUSE (RP) |
    | pure identifier | ≥2    | any                             | guarded     |
    | non-identifier  | 1     | any                             | direct      |
    | non-identifier  | ≥2    | return/assign/expr_stmt         | guarded_temp|
    | non-identifier  | ≥2    | comp/lambda/if/while/assert     | REFUSE (SE) |

    Identifier + 1 impl is refused (Receiver Pinning): emitting 'direct' would pin
    the call to one concrete type without a guard, breaking duck-typed objects.
    Non-identifier + ≥2 impls in unhoistable contexts is refused (Single Evaluation):
    the transformer cannot safely hoist the temp assignment before those statements.
    """

    REFUSED_RECEIVER_REEVAL = "REFUSED_RECEIVER_REEVAL"

    def __init__(
        self, site: CallSite, receiver_types: list[str], source: str
    ) -> None:
        self._site = site
        self._n_impls = len(receiver_types)
        self._source = source

    def must_refuse(self) -> bool:
        """True when rewriting would violate RP or SE invariants.

        RP (Receiver Pinning): identifier receiver that is a function parameter + 1 impl →
        'direct' would pin the call to one concrete type without an isinstance guard.
        A parameter can receive any compatible object at runtime; the planner must refuse
        rather than emit an unsound static binding.

        Local variable receivers (x = Worker(); x.method()) are not refused because
        the assignment context pins the type, and the isinstance fallback in guarded
        rewrites handles any duck-typed caller.

        SE (Single Evaluation): non-identifier receiver + ≥2 impls in a context
        where the transformer cannot hoist a temp assignment → refuse.
        """
        if self._site.receiver_expr.isidentifier():
            if self._n_impls == 1:
                # Refuse only when receiver is an untyped function parameter (RP).
                # Local-variable receivers with 1 observed impl are allowed (direct).
                return _is_receiver_a_function_parameter(self._source, self._site)
            # Identifier + ≥2 impls: 'guarded' strategy is safe (identifier evaluated once).
            return False
        # Non-identifier + 1 impl: 'direct' is safe (no re-eval needed).
        if self._n_impls <= 1:
            return False
        # Non-identifier + ≥2 impls: check whether temp hoisting is possible.
        return _is_call_site_in_unhoistable_context(self._source, self._site)

    def strategy(self) -> str:
        if self._n_impls == 1:
            return "direct"
        if self._site.receiver_expr.isidentifier():
            return "guarded"
        return "guarded_temp"

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

        # Phase 2: conservative verdict merge — same method_qualname → pick least permissive.
        verdict_by_method: dict[str, ClosureVerdict] = {}
        colliding_keys: set[str] = set()
        for v in verdicts:
            key = v.method_qualname
            if key in verdict_by_method:
                colliding_keys.add(key)
                verdict_by_method[key] = _most_conservative(verdict_by_method[key], v)
            else:
                verdict_by_method[key] = v

        decisions: dict[str, RewriteDecision] = {}
        for v in verdict_by_method.values():
            d = _with_proof(RewriteDecision.from_verdict(v))
            if v.method_qualname in colliding_keys:
                d = replace(
                    d,
                    message=f"{d.message} CONFLICTING_VERDICTS_RESOLVED_CONSERVATIVE",
                )
            decisions[v.method_qualname] = d

        observations_by_site: dict[str, list[ObservationRecord]] = defaultdict(list)
        for record in observations:
            observations_by_site[record.call_site_id].append(record)

        plans: list[TransformPlan] = []
        for site in call_sites:
            site_observations = observations_by_site.get(site.call_site_id, [])
            if not site_observations:
                continue

            # P0-2: Polymorphic sites yield one verdict per concrete override.
            # Require ALL to authorize and merge known_impls.
            method_keys = {
                _observation_method_qualname(record) for record in site_observations
            }
            site_verdicts = [
                verdict_by_method[key] for key in method_keys if key in verdict_by_method
            ]
            if not site_verdicts:
                continue

            site_decisions = [decisions.get(v.method_qualname) for v in site_verdicts]
            if any(
                d is None or not d.allowed or d.proof_status != "safe"
                for d in site_decisions
            ):
                continue

            # Merge known_impls from all verdicts
            merged_impls: list[type] = []
            for v in site_verdicts:
                for impl in v.known_impls:
                    if impl not in merged_impls:
                        merged_impls.append(impl)
            verdict = replace(site_verdicts[0], known_impls=merged_impls)

            receiver_types = _ordered_receiver_types(
                {observation_type_name(record) for record in site_observations},
                verdict,
            )
            if not receiver_types:
                continue

            # Phase 1: EvaluationSafety — refuse sites that would violate SI.
            eval_safety = EvaluationSafety(site, receiver_types, source)
            if eval_safety.must_refuse():
                # Non-identifier receiver + ≥2 impls + comprehension/lambda → REFUSE.
                # Rewriting would re-evaluate the receiver, violating SI evaluation-count.
                continue

            strategy = eval_safety.strategy()
            temp_receiver = ""
            receiver_expr = ""
            receiver_override = None
            if strategy == "guarded_temp":
                temp_receiver = _unique_temp_name(source, len(plans))
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


def _is_receiver_a_function_parameter(source: str, site: CallSite) -> bool:
    """Return True if the receiver identifier is a parameter of its enclosing function.

    Parameters are unpinned — the caller can pass any compatible object, so emitting
    a direct (unguarded) static call violates Receiver Pinning.  Local variables
    assigned within the function body are not parameters and are not refused here.
    """
    import ast as _ast

    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return False

    receiver = site.receiver_expr
    call_line = site.line

    best_func: _ast.FunctionDef | _ast.AsyncFunctionDef | None = None
    best_start = -1

    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", None) or node.lineno
            if node.lineno <= call_line <= end and node.lineno > best_start:
                best_start = node.lineno
                best_func = node

    if best_func is None:
        return False

    args = best_func.args
    param_names: set[str] = set(
        [a.arg for a in args.args]
        + [a.arg for a in args.posonlyargs]
        + [a.arg for a in args.kwonlyargs]
        + ([args.vararg.arg] if args.vararg else [])
        + ([args.kwarg.arg] if args.kwarg else [])
    )
    return receiver in param_names


def _is_call_site_in_unhoistable_context(source: str, site: CallSite) -> bool:
    """Return True when the call site is in a context where temp hoisting is impossible.

    Unhoistable contexts:
    - Comprehension iteration (CompFor) — hoist would escape the comprehension scope
    - Lambda body — hoist cannot precede a lambda expression
    - If-statement test — PositionRewriteTransformer only handles SimpleStatementLine
    - While-statement test — same; and re-hoisting per iteration is structurally unsound
    - Assert statement — leave_SimpleStatementLine excludes cst.Assert from hoist targets
    """
    try:
        from libcst.metadata import MetadataWrapper, PositionProvider
        module = cst.parse_module(source)
        wrapper = MetadataWrapper(module)
    except Exception:
        return False

    unsafe_ranges: list[tuple[int, int, int, int]] = []

    class UnhoistableVisitor(cst.CSTVisitor):
        METADATA_DEPENDENCIES = (PositionProvider,)

        def _record(self, node: cst.CSTNode) -> None:
            try:
                pos = self.get_metadata(PositionProvider, node)
                unsafe_ranges.append(
                    (pos.start.line, pos.start.column, pos.end.line, pos.end.column)
                )
            except Exception:
                pass

        def visit_CompFor(self, node: cst.CompFor) -> None:
            self._record(node)

        def visit_Lambda(self, node: cst.Lambda) -> None:
            self._record(node)

        def visit_If(self, node: cst.If) -> None:
            self._record(node.test)

        def visit_While(self, node: cst.While) -> None:
            self._record(node.test)

        def visit_Assert(self, node: cst.Assert) -> None:
            self._record(node)

    try:
        visitor = UnhoistableVisitor()
        wrapper.visit(visitor)
    except Exception:
        return False

    site_line, site_col = site.line, site.column
    for start_line, start_col, end_line, end_col in unsafe_ranges:
        if start_line <= site_line <= end_line:
            if start_line < site_line < end_line:
                return True
            if site_line == start_line and site_col >= start_col:
                return True
            if site_line == end_line and site_col <= end_col:
                return True
    return False


def _is_call_site_in_comprehension_or_lambda(source: str, site: CallSite) -> bool:
    """Legacy alias kept for any external callers; delegates to the broader check."""
    return _is_call_site_in_unhoistable_context(source, site)


def _unique_temp_name(source: str, plan_count: int) -> str:
    """Return a temp-receiver name that does not appear anywhere in source."""
    n = plan_count + 1
    while f"_flatten_receiver_{n}" in source:
        n += 1
    return f"_flatten_receiver_{n}"


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


def _observation_method_qualname(record: ObservationRecord) -> str:
    if record.qualname:
        return record.qualname
    resolved = record.resolved_function
    if hasattr(resolved, "qualname"):
        return str(resolved.qualname)
    text = str(resolved)
    return text.rsplit(".", 2)[-2] + "." + text.rsplit(".", 1)[-1]


@functools.lru_cache(maxsize=32)
def _parsed_calls_and_sites(source: str, filename: str) -> tuple[list[cst.Call], list[CallSite]]:
    """Parse source once and return (attribute-calls, discovered call sites) cached by content."""
    from flatten.discovery import discover_call_sites as _discover

    module = cst.parse_module(source)
    found: list[cst.Call] = []

    class Finder(cst.CSTVisitor):
        METADATA_DEPENDENCIES = ()

        def visit_Call(self, node: cst.Call) -> None:
            if isinstance(node.func, cst.Attribute):
                found.append(node)

    module.visit(Finder())
    sites = _discover(source, filename=filename)
    return found, sites


def _call_at_site(source: str, site: CallSite) -> cst.Call:
    found, sites = _parsed_calls_and_sites(source, site.filename)
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
