"""Command implementations for the flatten CLI (analyze, trace, plan, rewrite, verify)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import libcst as cst

from flatten._cli_io import (
    _decision_from_json,
    _decision_to_json,
    _entry_func,
    _json_print,
    _load_cases,
    _load_observations,
    _read,
    _restore_type,
    _source_hash,
    _verdict_to_json,
)
from flatten._utils import normalize_filename as _normalize_filename
from flatten.benchmarks import (
    load_benchmark_catalog,
    summarize_benchmark_catalog,
    write_benchmark_reports,
)
from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import (
    CallSite,
    ClosureStatus,
    ClosureVerdict,
    RewriteDecision,
    TransformPlan,
)
from flatten.discovery import discover_call_sites
from flatten.evaluation import evaluate_artifacts
from flatten.harness import assert_equivalent
from flatten.observations import (
    FunctionRef,
    ObservationRecord,
    TypeRef,
    observation_function_name,
    observation_type_name,
    observations_to_json,
    type_ref,
)
from flatten.planner import RewritePlanner
from flatten.report import AnalysisReport
from flatten.static import analyze_class_hierarchy
from flatten.tracer import Tracer


def _verdicts_from_observations(
    observations: list[ObservationRecord],
    *,
    closed_world: bool = False,
    source_path: Path | None = None,
) -> list[Any]:
    """Derive ClosureVerdict list from observed dispatch records.

    Args:
        observations: Bound observation records (must have call_site_id).
        closed_world: If True, assume no external subclasses exist.
        source_path: Path to the source file for static analysis enrichment.

    Returns:
        List of ClosureVerdict objects, one per unique method qualname.
    """
    if not observations:
        return []
    grouped: dict[str, list[ObservationRecord]] = {}
    for record in observations:
        grouped.setdefault(_method_qualname_from_observation(record), []).append(record)

    verdicts: list[ClosureVerdict] = []
    for method_qualname, records in grouped.items():
        observed_impls: list[type] = []
        for record in records:
            restored = _restore_type(record.receiver_type, source_path)
            if restored is None:
                verdicts.append(
                    ClosureVerdict(
                        method_qualname=method_qualname,
                        known_impls=[],
                        open_signals=["type restoration failed for observed receiver"],
                        signal="UNKNOWN",
                        rationale="cannot prove closed without restoring observed type objects",
                        status=ClosureStatus.UNKNOWN,
                        blockers=("type restoration failed for observed receiver",),
                        evidence=("loaded observation file",),
                    )
                )
                break
            if restored not in observed_impls:
                observed_impls.append(restored)
        else:
            checker = ClosureChecker(ClosureConfig(closed_world=closed_world))
            if source_path is not None and source_path.exists():
                source = _read(source_path)
                static_analysis = analyze_class_hierarchy(
                    source,
                    filename=str(source_path).replace("\\", "/"),
                    module_name=observed_impls[0].__module__,
                )
                if "class-attribute-assignment" in static_analysis.risk_flags:
                    verdicts.append(
                        ClosureVerdict(
                            method_qualname=method_qualname,
                            known_impls=observed_impls,
                            open_signals=[
                                "UNSAFE: possible monkey patch via class attribute assignment"
                            ],
                            signal="UNSAFE",
                            rationale=(
                                "cannot prove closed when source mutates class attributes"
                            ),
                            status=ClosureStatus.UNSAFE,
                            blockers=(
                                "UNSAFE: possible monkey patch via class attribute assignment",
                            ),
                            evidence=("checked static class attribute assignments",),
                        )
                    )
                    continue
                if "setattr" in static_analysis.risk_flags:
                    verdicts.append(
                        ClosureVerdict(
                            method_qualname=method_qualname,
                            known_impls=observed_impls,
                            open_signals=["UNSAFE: possible monkey patch via setattr"],
                            signal="UNSAFE",
                            rationale="cannot prove closed when source calls setattr",
                            status=ClosureStatus.UNSAFE,
                            blockers=("UNSAFE: possible monkey patch via setattr",),
                            evidence=("checked setattr calls",),
                        )
                    )
                    continue
                checker = ClosureChecker(
                    ClosureConfig(
                        closed_world=closed_world,
                        static_known_classes=frozenset(static_analysis.classes),
                        static_subclasses=static_analysis.subclasses,
                        use_runtime_subclasses_for_closure=False,
                    )
                )
            verdicts.append(checker.check(method_qualname, observed_impls))
    return verdicts


def _method_qualname_from_observation(record: ObservationRecord) -> str:
    """Extract the method qualname (e.g. 'MyClass.method') from an observation record."""
    if record.qualname:
        return record.qualname
    if isinstance(record.resolved_function, FunctionRef):
        return record.resolved_function.qualname
    text = observation_function_name(record)
    if record.method_name:
        owner = text.rsplit(".", 1)[0].rsplit(".", 1)[-1]
        return f"{owner}.{record.method_name}"
    return text.rsplit(".", 2)[-2] + "." + text.rsplit(".", 1)[-1]


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run static analysis on a Python source file and print a JSON report.

    Args:
        args: Parsed CLI args with optional ``path`` and ``format`` fields.

    Returns:
        Exit code 0 on success.
    """
    if args.path is not None:
        args.path = args.path.resolve()
    if args.path is None:
        source = ""
        filename = "<memory>"
    else:
        source = _read(args.path)
        filename = str(args.path).replace("\\", "/")
    call_sites = discover_call_sites(source, filename=filename)
    module_name = args.path.stem if args.path else "__main__"
    static_analysis = analyze_class_hierarchy(
        source,
        filename=filename,
        module_name=module_name,
    )
    payload = {
        "confidence": 0.0,
        "summary": f"found {len(call_sites)} method call candidate(s)",
        "call_sites": [site.__dict__ for site in call_sites],
        "verdicts": [],
        "static_analysis": {
            "classes": {
                name: {
                    "bases": list(info.bases),
                    "methods": sorted(info.methods),
                    "is_final": info.is_final,
                    "risk_flags": sorted(info.risk_flags),
                }
                for name, info in static_analysis.classes.items()
            },
            "subclasses": {
                name: sorted(children)
                for name, children in static_analysis.subclasses.items()
            },
            "method_overrides": {
                name: sorted(owners)
                for name, owners in static_analysis.method_overrides.items()
            },
            "risk_flags": sorted(static_analysis.risk_flags),
        },
        "metadata": {"path": str(args.path) if args.path else None},
        "errors": [],
    }
    if args.format == "html":
        print(AnalysisReport([], confidence=0.0, metadata=payload).to_html())
    else:
        _json_print(payload)
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Trace a Python entry function and write observed dispatch records.

    Args:
        args: Parsed CLI args with ``path``, ``entry``, ``out``, ``strict``,
              and ``capture_values`` fields.

    Returns:
        Exit code 0 on success, 2 if unbound observations exist and ``--strict``.
    """
    args.path = args.path.resolve()
    if args.out is not None:
        args.out = args.out.resolve()
    fn = _entry_func(args.path, args.entry)
    call_sites = discover_call_sites(
        _read(args.path),
        filename=str(args.path).replace("\\", "/"),
    )
    with Tracer(capture_values=args.capture_values) as tracer:
        fn()
    records = [
        _observation_from_trace(record, call_sites, index)
        for index, record in enumerate(tracer.records, start=1)
        if record.is_dispatch_target and record.impl_class is not None
    ]
    bound_count = sum(1 for record in records if record.call_site_id)
    unbound_count = len(records) - bound_count
    payload = observations_to_json(records)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    if unbound_count:
        print(
            f"flatten: warning: bound {bound_count} / unbound {unbound_count} observation(s)",
            file=sys.stderr,
        )
        if args.strict:
            return 2
    return 0


def _observation_from_trace(
    record: Any,
    call_sites: list[Any],
    index: int,
) -> ObservationRecord:
    """Convert a raw OracleRecord into a bound ObservationRecord."""
    traced_method_name = record.qualname.rsplit(".", 1)[-1]
    caller_filename = _normalize_filename(str(getattr(record, "caller_filename", "")))
    caller_lineno = int(getattr(record, "caller_lineno", 0))
    caller_column = int(getattr(record, "caller_column", -1))
    candidates = [
        site
        for site in call_sites
        if (
            site.filename == caller_filename
            and site.line == caller_lineno
            and site.method_name == traced_method_name
        )
    ]
    if len(candidates) > 1 and caller_column >= 0:
        column_matches = [
            site
            for site in candidates
            if site.column <= caller_column < site.end_column
        ]
        if len(column_matches) == 1:
            candidates = column_matches
    site = candidates[0] if len(candidates) == 1 else None
    method_name = site.method_name if site is not None else traced_method_name
    method = getattr(record.impl_class, method_name, None)
    resolved = FunctionRef(
        module=record.impl_class.__module__,
        qualname=f"{record.impl_class.__qualname__}.{method_name}",
        file=getattr(getattr(method, "__code__", None), "co_filename", None),
        firstlineno=getattr(getattr(method, "__code__", None), "co_firstlineno", None),
    )
    receiver = type_ref(record.impl_class)
    return ObservationRecord(
        call_site_id=site.call_site_id if site is not None else "",
        receiver_type=receiver,
        resolved_function=resolved,
        method_name=method_name,
        frame_module=record.impl_class.__module__,
        order=index,
        input_hash=hashlib.sha256(
            f"{index}:{record.args!r}:{record.kwargs!r}".encode()
        ).hexdigest(),
        module=record.impl_class.__module__,
        qualname=f"{record.impl_class.__qualname__}.{method_name}",
    )


def _make_plans(
    args: argparse.Namespace,
) -> tuple[list[Any], list[Any], list[Any], list[RewriteDecision], int]:
    """Load source, observations, and verdicts; produce rewrite plans.

    Returns:
        (call_sites, verdicts, plans, decisions, unbound_count)
    """
    args.path = args.path.resolve()
    args.observations = args.observations.resolve()
    source = _read(args.path)
    call_sites = discover_call_sites(source, filename=str(args.path).replace("\\", "/"))
    observations = _load_observations(args.observations)
    bound_observations = [record for record in observations if record.call_site_id]
    unbound_count = len(observations) - len(bound_observations)
    verdicts = _verdicts_from_observations(
        bound_observations,
        closed_world=args.closed_world,
        source_path=args.path,
    )
    planner = RewritePlanner(opt_in=True)
    decisions = planner.decide(verdicts)
    plans = planner.plan_from_observations(
        source,
        call_sites,
        bound_observations,
        verdicts,
    )
    return call_sites, verdicts, plans, decisions, unbound_count


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate rewrite plans from observations and write them to a JSON file.

    Args:
        args: Parsed CLI args with ``path``, ``observations``, ``out``, ``strict`` fields.

    Returns:
        Exit code 0 on success, 2 if no plans and unbound observations with ``--strict``.
    """
    call_sites, verdicts, plans, decisions, unbound_count = _make_plans(args)
    source = _read(args.path)
    observations = _load_observations(args.observations)
    payload = {
        "summary": f"created {len(plans)} rewrite plan(s)",
        "source_hash": _source_hash(source),
        "call_sites": [site.__dict__ for site in call_sites],
        "verdicts": [_verdict_to_json(verdict) for verdict in verdicts],
        "rewrite_decisions": [_decision_to_json(decision) for decision in decisions],
        "rewrite_plans": [
            _plan_to_json(plan, observations)
            for plan in plans
        ],
        "unbound_observations": unbound_count,
    }
    if args.out:
        args.out = args.out.resolve()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        _json_print(payload)
    if not plans and unbound_count:
        print(
            f"flatten: warning: {unbound_count} unbound observation(s); "
            "no rewrite plans created",
            file=sys.stderr,
        )
        if args.strict:
            return 2
    return 0


def _plan_to_json(
    plan: TransformPlan,
    observations: list[ObservationRecord],
) -> dict[str, Any]:
    """Serialize a TransformPlan to a JSON-compatible dict."""
    call_site_id = plan.target_call_site.call_site_id if plan.target_call_site else None
    return {
        "call_site_id": call_site_id,
        "strategy": plan.strategy,
        "reason": plan.rationale,
        "confidence": plan.confidence,
        "risk_flags": plan.risk_flags,
        "target_range": plan.target_range,
        "replacement": cst.Module([]).code_for_node(plan.replacement),
        "temp_receiver": plan.temp_receiver,
        "receiver_expr": plan.receiver_expr,
        "verdict": _verdict_to_json(plan.verdict),
        "proof_artifact": _proof_artifact_for_plan(plan, observations),
    }


def _proof_artifact_for_plan(
    plan: TransformPlan,
    observations: list[ObservationRecord],
) -> dict[str, Any]:
    """Build a proof artifact dict for a rewrite plan (used for audit trails)."""
    call_site_id = plan.target_call_site.call_site_id if plan.target_call_site else ""
    observed_targets = sorted(
        {
            observation_type_name(record)
            for record in observations
            if record.call_site_id == call_site_id
        }
    )
    verdict = plan.verdict
    status = verdict.status.value if verdict.status else verdict.signal.lower()
    return {
        "callsite": call_site_id,
        "observed_targets": observed_targets,
        "closure_status": status,
        "closure_rules_passed": list(verdict.evidence),
        "closure_rules_failed": list(verdict.blockers or verdict.open_signals),
        "risk_level": "safe" if status == ClosureStatus.CLOSED.value else "unsafe",
        "rewrite_allowed": status == ClosureStatus.CLOSED.value and not verdict.blockers,
    }


def cmd_rewrite(args: argparse.Namespace) -> int:
    """Rewrite a source file to flatten observed polymorphic dispatch.

    Args:
        args: Parsed CLI args with ``path``, ``out``, ``observations``, ``plan``,
              ``apply``, ``dry_run``, ``entry``, ``cases``, ``skip_verify``, ``strict``.

    Returns:
        Exit code 0 on success, 1 on error, 2 if rewrites were skipped and ``--strict``
        (exit code 2 if rewrites were skipped due to low confidence, only with --strict).

    Raises:
        AssertionError: If the rewritten function is not equivalent to the original.
    """
    args.path = args.path.resolve()
    args.out = args.out.resolve()
    if args.observations is not None:
        args.observations = args.observations.resolve()
    if args.plan is not None:
        args.plan = args.plan.resolve()
    if args.plan:
        plans = _plans_from_plan_file(args.plan, _read(args.path))
        verdicts: list[Any] = []
        decisions: list[RewriteDecision] = []
    else:
        _, verdicts, plans, decisions, _ = _make_plans(args)
    if args.dry_run or not args.apply:
        _json_print(
            {
                "summary": "dry run only; pass --apply to write output",
                "rewrite_plans": len(plans),
                "verdicts": [_verdict_to_json(verdict) for verdict in verdicts],
                "rewrite_decisions": [
                    _decision_to_json(decision) for decision in decisions
                ],
            }
        )
        return 0
    if not args.skip_verify and not args.entry:
        print("flatten: error: rewrite --apply requires --entry or --skip-verify", file=sys.stderr)
        return 1
    if not args.skip_verify and args.entry and args.cases is None:
        print("flatten: error: rewrite --apply --entry requires --cases", file=sys.stderr)
        return 1
    rewritten = RewritePlanner(opt_in=True).rewrite_source(_read(args.path), plans)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rewritten, encoding="utf-8")
    if not args.skip_verify and args.entry:
        original = _entry_func(args.path, args.entry, "_original")
        rewritten_entry = _entry_func(args.out, args.entry, "_rewritten")
        assert_equivalent(original, rewritten_entry, _load_cases(args.cases))
    summary = (
        f"wrote {args.out}; applied 0 rewrite plan(s)"
        if not plans
        else f"wrote {args.out}"
    )
    _json_print({"summary": summary, "rewrite_plans": len(plans)})
    if not plans and args.strict:
        return 2
    return 0


def _plans_from_plan_file(path: Path, source: str) -> list[Any]:
    """Load and validate TransformPlan list from a plan JSON file."""
    raw = json.loads(_read(path.resolve()))
    source_class_names = _top_level_class_names(source)
    if raw.get("source_hash") != _source_hash(source):
        raise ValueError("untrusted plan: source hash missing or does not match")
    plans: list[Any] = []
    for item in raw.get("rewrite_plans", []):
        verdict_raw = item.get("verdict")
        if not isinstance(verdict_raw, dict):
            raise ValueError("untrusted plan: missing serialized verdict")
        status = str(verdict_raw.get("status", verdict_raw.get("signal", ""))).lower()
        evidence = tuple(str(value) for value in verdict_raw.get("evidence", []))
        if status != ClosureStatus.CLOSED.value or not evidence:
            raise ValueError("untrusted plan: verdict is not revalidated CLOSED evidence")
        replacement_text = str(item["replacement"])
        for class_name in _class_names_referenced_by_replacement(replacement_text):
            if class_name not in source_class_names:
                raise ValueError(
                    f"untrusted plan: class name not in source scope: {class_name}"
                )
        decisions = raw.get("rewrite_decisions")
        if not isinstance(decisions, list) or not decisions:
            raise ValueError("untrusted plan: missing rewrite decisions")
        artifact = item.get("proof_artifact")
        if not isinstance(artifact, dict) or artifact.get("rewrite_allowed") is not True:
            raise ValueError("untrusted plan: missing positive proof artifact")
        replacement = cst.parse_expression(item["replacement"])
        verdict = ClosureVerdict(
            method_qualname="",
            known_impls=[],
            signal="CLOSED",
            rationale=item.get("reason", "plan file"),
            status=ClosureStatus.CLOSED,
            evidence=evidence,
        )
        target_range = item.get("target_range")
        strategy = item.get("strategy", "direct")
        temp_receiver = str(item.get("temp_receiver", ""))
        receiver_expr = str(item.get("receiver_expr", ""))
        call_site_id = item.get("call_site_id", "")
        target_call_site = _call_site_for_range(source, call_site_id, target_range)

        if strategy == "guarded_temp" and (
            target_call_site is None or not temp_receiver or not receiver_expr
        ):
            raise ValueError(
                "untrusted plan: guarded_temp plan missing receiver hoist metadata"
            )

        plans.append(
            TransformPlan(
                target_node=None,
                replacement=replacement,
                verdict=verdict,
                rationale=item.get("reason", ""),
                target_range=target_range,
                target_call_site=target_call_site,
                strategy=strategy,
                confidence=float(item.get("confidence", 0.0)),
                risk_flags=list(item.get("risk_flags", [])),
                temp_receiver=temp_receiver,
                receiver_expr=receiver_expr,
            )
        )
    return plans


def _call_site_for_range(
    source: str, call_site_id: str, target_range: str | None
) -> CallSite | None:
    """Reconstruct a CallSite from plan metadata by matching id or position range."""
    filename = call_site_id.split(":", 1)[0] if ":" in call_site_id else "<memory>"
    for site in discover_call_sites(source, filename=filename):
        if site.call_site_id == call_site_id:
            return site
        if target_range and (
            f"{site.line}:{site.column}-{site.end_line}:{site.end_column}" == target_range
        ):
            return site
    return None


def _top_level_class_names(source: str) -> set[str]:
    """Return the set of top-level class names defined in source."""
    module = cst.parse_module(source)
    return {
        statement.name.value
        for statement in module.body
        if isinstance(statement, cst.ClassDef)
    }


def _class_names_referenced_by_replacement(replacement: str) -> set[str]:
    """Return class names (title-case Name in Attribute) referenced by replacement expression."""
    expression = cst.parse_expression(replacement)
    names: set[str] = set()

    class Visitor(cst.CSTVisitor):
        def visit_Attribute(self, node: cst.Attribute) -> None:
            if isinstance(node.value, cst.Name):
                name = node.value.value
                if name[:1].isupper():
                    names.add(name)

    expression.visit(Visitor())
    return names


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify that original and rewritten entry functions are behaviorally equivalent.

    Args:
        args: Parsed CLI args with ``original``, ``rewritten``, ``entry``, ``cases`` fields.

    Returns:
        Exit code 0 if equivalent.

    Raises:
        AssertionError: If the functions produce different outputs on any test case.
    """
    args.original = args.original.resolve()
    args.rewritten = args.rewritten.resolve()
    if args.cases is not None:
        args.cases = args.cases.resolve()
    original = _entry_func(args.original, args.entry, "_original")
    rewritten = _entry_func(args.rewritten, args.entry, "_rewritten")
    cases = _load_cases(args.cases) if args.cases else [((), {})]
    assert_equivalent(original, rewritten, cases)
    coverage = "minimal" if len(cases) <= 1 else "cases"
    _json_print(
        {
            "summary": "equivalent",
            "equivalent": True,
            "cases": len(cases),
            "verification_coverage": coverage,
            "warnings": ["verification coverage: minimal"] if coverage == "minimal" else [],
        }
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Print a human-readable summary of a plan JSON file.

    Args:
        args: Parsed CLI args with ``plan`` field.

    Returns:
        Exit code 0.
    """
    args.plan = args.plan.resolve()
    payload = json.loads(_read(args.plan))
    verdicts = payload.get("verdicts", [])
    plans = payload.get("rewrite_plans", [])
    print(payload.get("summary", "flatten plan report"))
    print(f"rewrite plans: {len(plans)}")
    for verdict in verdicts:
        print(f"{verdict.get('signal', 'UNKNOWN')}: {verdict.get('rationale', '')}")
        for signal in verdict.get("open_signals", []):
            print(f"- {signal}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate rewrite artifacts for a source file and print a JSON report.

    Args:
        args: Parsed CLI args with ``path`` and optional ``plan`` fields.

    Returns:
        Exit code 0.
    """
    args.path = args.path.resolve()
    source = _read(args.path)
    call_sites = discover_call_sites(source, filename=str(args.path).replace("\\", "/"))
    decisions: list[RewriteDecision] = []
    if args.plan is not None:
        payload = json.loads(_read(args.plan.resolve()))
        decisions = [
            _decision_from_json(item)
            for item in payload.get("rewrite_decisions", [])
            if isinstance(item, dict)
        ]
    _json_print(evaluate_artifacts(call_sites, decisions).to_json())
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run benchmark catalog and write summary reports.

    Args:
        args: Parsed CLI args with ``catalog``, ``out_json``, ``out_md`` fields.

    Returns:
        Exit code 0.
    """
    projects = load_benchmark_catalog(args.catalog.resolve())
    summary = summarize_benchmark_catalog(projects)
    write_benchmark_reports(
        summary,
        out_json=args.out_json.resolve() if args.out_json else None,
        out_md=args.out_md.resolve() if args.out_md else None,
    )
    _json_print(summary)
    return 0
