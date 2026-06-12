"""Command line interface for flatten."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import libcst as cst

from flatten.closure import ClosureChecker, ClosureConfig
from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision, TransformPlan
from flatten.discovery import discover_call_sites
from flatten.evaluation import evaluate_artifacts
from flatten.harness import assert_equivalent
from flatten.observations import (
    FunctionRef,
    ObservationRecord,
    TypeRef,
    observation_function_name,
    observations_from_json,
    observations_to_json,
    type_ref,
)
from flatten.planner import RewritePlanner
from flatten.report import AnalysisReport
from flatten.static import analyze_class_hierarchy
from flatten.tracer import Tracer


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_observations(path: Path) -> list[ObservationRecord]:
    return observations_from_json(_read(path.resolve()))


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _verdict_to_json(verdict: ClosureVerdict) -> dict[str, Any]:
    return {
        "method_qualname": verdict.method_qualname,
        "is_closed": verdict.is_closed,
        "known_impls": [
            f"{impl.__module__}.{impl.__qualname__}" if isinstance(impl, type) else str(impl)
            for impl in verdict.known_impls
        ],
        "open_signals": list(verdict.open_signals),
        "signal": verdict.signal,
        "rationale": verdict.rationale,
        "status": verdict.status.value if verdict.status else verdict.signal.lower(),
        "confidence": verdict.confidence,
        "reasons": list(verdict.reasons),
        "blockers": list(verdict.blockers),
        "evidence": list(verdict.evidence),
    }


def _decision_to_json(decision: RewriteDecision) -> dict[str, Any]:
    return decision.to_json()


def _ref_attr(module: Any, qualname: str) -> Any:
    value = module
    for part in qualname.split("."):
        value = getattr(value, part)
    return value


def _restore_type(ref: Any, fallback_path: Path | None = None) -> type | None:
    if isinstance(ref, str):
        module_name, _, qualname = ref.rpartition(".")
        if not module_name or not qualname:
            return None
        module = sys.modules.get(module_name)
        if fallback_path is not None and _module_file(module) != fallback_path:
            module = _load_module(fallback_path, module_name)
        if module is None:
            return None
        value = _ref_attr(module, qualname)
        return value if isinstance(value, type) else None

    if not isinstance(ref, TypeRef) or ref.is_builtin:
        return None
    if ref.file is None and fallback_path is None:
        return None
    path = Path(ref.file) if ref.file is not None else fallback_path
    if path is None:
        return None
    if not path.exists():
        return None
    module = sys.modules.get(ref.module)
    if _module_file(module) != path:
        module = _load_module(path, ref.module)
    value = _ref_attr(module, ref.qualname)
    return value if isinstance(value, type) else None


def _module_file(module: Any) -> Path | None:
    if module is None:
        return None
    filename = getattr(module, "__file__", None)
    if filename is None:
        return None
    return Path(filename).resolve()


def _entry_func(path: Path, entry: str, suffix: str = "") -> Any:
    path = path.resolve()
    module_name, _, function_name = entry.partition(":")
    if not module_name or not function_name:
        raise ValueError("--entry must use module:function")
    module = _load_module(path, f"_flatten_{module_name.replace('.', '_')}{suffix}")
    try:
        return getattr(module, function_name)
    except AttributeError as exc:
        raise ValueError(f"entry function not found: {entry}") from exc


def _verdicts_from_observations(
    observations: list[ObservationRecord],
    *,
    closed_world: bool = False,
    source_path: Path | None = None,
) -> list[Any]:
    if not observations:
        return []
    first = observations[0]
    method_qualname = first.qualname or (
        first.resolved_function.qualname
        if isinstance(first.resolved_function, FunctionRef)
        else observation_function_name(first).rsplit(".", 2)[-2]
        + "."
        + (first.method_name or observation_function_name(first).rsplit(".", 1)[-1])
    )
    observed_impls: list[type] = []
    for record in observations:
        restored = _restore_type(record.receiver_type, source_path)
        if restored is None:
            return [
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
            ]
        if restored not in observed_impls:
            observed_impls.append(restored)
    checker = ClosureChecker(ClosureConfig(closed_world=closed_world))
    if source_path is not None and source_path.exists():
        source = _read(source_path)
        static_analysis = analyze_class_hierarchy(
            source,
            filename=str(source_path).replace("\\", "/"),
            module_name=observed_impls[0].__module__,
        )
        if "class-attribute-assignment" in static_analysis.risk_flags:
            return [
                ClosureVerdict(
                    method_qualname=method_qualname,
                    known_impls=observed_impls,
                    open_signals=["UNSAFE: possible monkey patch via class attribute assignment"],
                    signal="UNSAFE",
                    rationale="cannot prove closed when source mutates class attributes",
                    status=ClosureStatus.UNSAFE,
                    blockers=("UNSAFE: possible monkey patch via class attribute assignment",),
                    evidence=("checked static class attribute assignments",),
                )
            ]
        checker = ClosureChecker(
            ClosureConfig(
                closed_world=closed_world,
                static_known_classes=frozenset(static_analysis.classes),
                static_subclasses=static_analysis.subclasses,
                use_runtime_subclasses_for_closure=False,
            )
        )
    return [checker.check(method_qualname, observed_impls)]


def cmd_analyze(args: argparse.Namespace) -> int:
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
    call_sites, verdicts, plans, decisions, unbound_count = _make_plans(args)
    source = _read(args.path)
    payload = {
        "summary": f"created {len(plans)} rewrite plan(s)",
        "source_hash": _source_hash(source),
        "call_sites": [site.__dict__ for site in call_sites],
        "verdicts": [_verdict_to_json(verdict) for verdict in verdicts],
        "rewrite_decisions": [_decision_to_json(decision) for decision in decisions],
        "rewrite_plans": [
            {
                "call_site_id": plan.target_call_site.call_site_id
                if plan.target_call_site
                else None,
                "strategy": plan.strategy,
                "reason": plan.rationale,
                "confidence": plan.confidence,
                "risk_flags": plan.risk_flags,
                "target_range": plan.target_range,
                "replacement": cst.Module([]).code_for_node(plan.replacement),
                "temp_receiver": plan.temp_receiver,
                "receiver_expr": plan.receiver_expr,
                "verdict": _verdict_to_json(plan.verdict),
            }
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


def cmd_rewrite(args: argparse.Namespace) -> int:
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
    rewritten = RewritePlanner(opt_in=True).rewrite_source(_read(args.path), plans)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rewritten, encoding="utf-8")
    if not args.skip_verify and args.entry:
        original = _entry_func(args.path, args.entry, "_original")
        rewritten_entry = _entry_func(args.out, args.entry, "_rewritten")
        assert_equivalent(original, rewritten_entry, [((), {})])
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
        replacement = cst.parse_expression(item["replacement"])
        verdict = ClosureVerdict(
            method_qualname="",
            known_impls=[],
            signal="CLOSED",
            rationale=item.get("reason", "plan file"),
            status=ClosureStatus.CLOSED,
            evidence=evidence,
        )
        plans.append(
            TransformPlan(
                target_node=None,
                replacement=replacement,
                verdict=verdict,
                rationale=item.get("reason", ""),
                target_range=item.get("target_range"),
                strategy=item.get("strategy", "direct"),
                confidence=float(item.get("confidence", 0.0)),
                risk_flags=list(item.get("risk_flags", [])),
            )
        )
    return plans


def _top_level_class_names(source: str) -> set[str]:
    module = cst.parse_module(source)
    return {
        statement.name.value
        for statement in module.body
        if isinstance(statement, cst.ClassDef)
    }


def _class_names_referenced_by_replacement(replacement: str) -> set[str]:
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


def _load_cases(path: Path) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    raw = json.loads(_read(path))
    if not isinstance(raw, list):
        raise ValueError("--cases must be a JSON list")
    cases: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            args = item.get("args", [])
            kwargs = item.get("kwargs", {})
        elif isinstance(item, list) and len(item) == 2:
            args, kwargs = item
        else:
            raise ValueError(f"case #{index} must be an object or [args, kwargs]")
        if not isinstance(args, list) or not isinstance(kwargs, dict):
            raise ValueError(f"case #{index} args must be list and kwargs must be object")
        cases.append((tuple(args), dict(kwargs)))
    return cases


def cmd_report(args: argparse.Namespace) -> int:
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


def _decision_from_json(raw: dict[str, Any]) -> RewriteDecision:
    status_text = str(raw.get("status", "unknown"))
    try:
        status = ClosureStatus(status_text)
    except ValueError:
        status = ClosureStatus.UNKNOWN
        raw = {
            **raw,
            "allowed": False,
            "blockers": [
                *raw.get("blockers", []),
                f"invalid rewrite decision status: {status_text}",
            ],
        }
    return RewriteDecision(
        method_qualname=str(raw.get("method_qualname", "")),
        allowed=bool(raw.get("allowed", False)),
        status=status,
        blockers=tuple(str(item) for item in raw.get("blockers", [])),
        reasons=tuple(str(item) for item in raw.get("reasons", [])),
        evidence=tuple(str(item) for item in raw.get("evidence", [])),
        reason_code=str(raw.get("reason_code", "")),
    )


def cmd_evaluate(args: argparse.Namespace) -> int:
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


def _normalize_filename(filename: str) -> str:
    if not filename or filename.startswith("<"):
        return filename
    return str(Path(filename).resolve()).replace("\\", "/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flatten")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("path", type=Path, nargs="?")
    analyze.add_argument("--format", choices=["json", "html"], default="json")
    analyze.add_argument("--json", action="store_const", dest="format", const="json")
    analyze.add_argument("--strict", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    trace = subparsers.add_parser("trace")
    trace.add_argument("path", type=Path)
    trace.add_argument("--entry", required=True)
    trace.add_argument("--out", type=Path)
    trace.add_argument("--json", action="store_true")
    trace.add_argument("--strict", action="store_true")
    trace.add_argument("--capture-values", action="store_true")
    trace.set_defaults(func=cmd_trace)

    plan = subparsers.add_parser("plan")
    plan.add_argument("path", type=Path)
    plan.add_argument("--observations", type=Path, required=True)
    plan.add_argument("--out", type=Path)
    plan.add_argument("--closed-world", action="store_true")
    plan.add_argument("--json", action="store_true")
    plan.add_argument("--strict", action="store_true")
    plan.set_defaults(func=cmd_plan)

    rewrite = subparsers.add_parser("rewrite")
    rewrite.add_argument("path", type=Path)
    rewrite.add_argument("--observations", type=Path)
    rewrite.add_argument("--plan", type=Path)
    rewrite.add_argument("--out", type=Path, required=True)
    rewrite.add_argument("--apply", action="store_true")
    rewrite.add_argument("--dry-run", action="store_true")
    rewrite.add_argument("--closed-world", action="store_true")
    rewrite.add_argument("--entry")
    rewrite.add_argument("--skip-verify", action="store_true")
    rewrite.add_argument("--json", action="store_true")
    rewrite.add_argument("--strict", action="store_true")
    rewrite.set_defaults(func=cmd_rewrite)

    verify = subparsers.add_parser("verify")
    verify.add_argument("original", type=Path)
    verify.add_argument("rewritten", type=Path)
    verify.add_argument("--entry", required=True)
    verify.add_argument("--cases", type=Path)
    verify.add_argument("--json", action="store_true")
    verify.add_argument("--strict", action="store_true")
    verify.set_defaults(func=cmd_verify)

    report = subparsers.add_parser("report")
    report.add_argument("plan", type=Path)
    report.add_argument("--json", action="store_true")
    report.add_argument("--strict", action="store_true")
    report.set_defaults(func=cmd_report)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--plan", type=Path)
    evaluate.add_argument("--json", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"flatten: error: {exc}", file=sys.stderr)
        return 1
