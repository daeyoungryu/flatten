"""Render a human-readable Capafy audit summary from flatten report JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"report field {key!r} must be a list of objects")
    return value


def _status(verdict: dict[str, Any]) -> str:
    return str(verdict.get("status") or verdict.get("signal") or "unknown").upper()


def _location(item: dict[str, Any]) -> str:
    call_site_id = item.get("call_site_id") or item.get("callsite")
    if call_site_id:
        parts = str(call_site_id).rsplit(":", 2)
        return ":".join(parts[:2]) if len(parts) == 3 else str(call_site_id)
    target_range = item.get("target_range")
    return str(target_range or "unknown location").split("-", 1)[0]


def _hazard(verdict: dict[str, Any]) -> str:
    for key in ("blockers", "open_signals", "risk_flags"):
        values = verdict.get(key)
        if isinstance(values, list) and values:
            return str(values[0])
    return str(verdict.get("rationale") or "unspecified unsafe condition")


def render_summary(
    report_path: Path,
    summary_path: Path,
    *,
    git_warning: str = "",
    top_n: int = 10,
) -> None:
    """Render ``summary_path`` using the existing plan-backed report fields."""
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report JSON must be an object")
    call_sites = _items(payload, "call_sites")
    verdicts = _items(payload, "verdicts")
    plans = _items(payload, "rewrite_plans")
    closed = [item for item in verdicts if _status(item) == "CLOSED"]
    unsafe = [item for item in verdicts if _status(item) == "UNSAFE"]

    lines: list[str] = []
    if git_warning:
        lines.extend(
            [
                "# WARNING: Repository changed during audit",
                "",
                "The filtered pre/post Git status snapshots differ:",
                "",
                "```text",
                git_warning.rstrip(),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "# Capafy read-only audit summary",
            "",
            f"- Total call sites: {len(call_sites)}",
            f"- CLOSED candidates: {len(closed)}",
            f"- UNSAFE: {len(unsafe)}",
            "",
            "## Top UNSAFE findings",
            "",
        ]
    )
    if unsafe:
        for verdict in unsafe[:top_n]:
            lines.append(f"- `{_location(verdict)}` — {_hazard(verdict)}")
    else:
        lines.append("- None reported.")
    lines.extend(["", "## Top rewrite candidates", ""])
    if plans:
        ranked = sorted(
            plans,
            key=lambda item: float(item.get("confidence", 0.0) or 0.0),
            reverse=True,
        )
        for plan in ranked[:top_n]:
            confidence = float(plan.get("confidence", 0.0) or 0.0)
            lines.append(
                f"- `{_location(plan)}` — confidence {confidence:.2f} "
                "(reference only; not applied)"
            )
    else:
        lines.append("- None reported (reference only; nothing was applied).")
    verdict = (
        "The audit found unsafe dispatch evidence that blocks sound transformation."
        if unsafe
        else "The audit found no UNSAFE verdicts in the collected evidence."
    )
    lines.extend(
        [
            "",
            "## Overall assessment",
            "",
            f"{verdict} CLOSED and rewrite-candidate counts are audit evidence only; "
            "this run did not modify or transform source code.",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")

