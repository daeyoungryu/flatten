"""I/O helpers for the flatten CLI: file reading, JSON serialization, module loading."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from flatten.contracts import ClosureStatus, ClosureVerdict, RewriteDecision
from flatten.observations import ObservationRecord, TypeRef, observations_from_json


def _read(path: Path) -> str:
    """Read a UTF-8 text file and return its contents."""
    return path.read_text(encoding="utf-8")


def _load_observations(path: Path) -> list[ObservationRecord]:
    """Load ObservationRecord list from a JSON file."""
    return observations_from_json(_read(path.resolve()))


def _json_print(payload: dict[str, Any]) -> None:
    """Pretty-print a dict as JSON to stdout."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _load_module(path: Path, module_name: str) -> Any:
    """Import a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Failed to load module from {path}: spec_from_file_location returned None"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"Failed to load module from {path}: {exc}") from exc
    return module


def _source_hash(source: str) -> str:
    """Return the SHA-256 hex digest of the UTF-8 encoded source string."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _verdict_to_json(verdict: ClosureVerdict) -> dict[str, Any]:
    """Serialize a ClosureVerdict to a JSON-compatible dict."""
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
    """Serialize a RewriteDecision to a JSON-compatible dict."""
    return decision.to_json()


def _decision_from_json(raw: dict[str, Any]) -> RewriteDecision:
    """Deserialize a RewriteDecision from a JSON-compatible dict."""
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
        proof_artifact=raw.get("proof_artifact")
        if isinstance(raw.get("proof_artifact"), dict)
        else None,
    )


def _ref_attr(module: Any, qualname: str) -> Any:
    """Traverse dotted attribute path on module."""
    value = module
    for part in qualname.split("."):
        value = getattr(value, part)
    return value


def _restore_type(ref: Any, fallback_path: Path | None = None) -> type | None:
    """Restore a Python type object from a TypeRef or dotted string."""
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
    """Return the resolved path of a module's source file, or None."""
    if module is None:
        return None
    filename = getattr(module, "__file__", None)
    if filename is None:
        return None
    return Path(filename).resolve()


def _entry_func(path: Path, entry: str, suffix: str = "") -> Any:
    """Load and return a function from a Python source file.

    Args:
        path: Path to the Python source file.
        entry: ``module:function`` specifier string.
        suffix: Optional suffix appended to the module name to avoid conflicts.

    Returns:
        The callable identified by *entry*.

    Raises:
        ValueError: If *entry* format is wrong or the function is not found.
    """
    path = path.resolve()
    module_name, _, function_name = entry.partition(":")
    if not module_name or not function_name:
        raise ValueError("--entry must use module:function")
    module = _load_module(path, f"_flatten_{module_name.replace('.', '_')}{suffix}")
    try:
        return getattr(module, function_name)
    except AttributeError as exc:
        raise ValueError(f"entry function not found: {entry}") from exc


def _load_cases(path: Path) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Load test cases from a JSON file as (args, kwargs) tuples.

    Args:
        path: Path to a JSON file containing a list of case objects.

    Returns:
        List of (args_tuple, kwargs_dict) pairs.

    Raises:
        ValueError: If the file format is invalid.
    """
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
