"""JSON and HTML reporting for flatten analysis."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from typing import Any

from flatten.contracts import ClosureVerdict
from flatten.evaluation import EvaluationMetrics


def _type_name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _verdict_to_dict(verdict: ClosureVerdict) -> dict[str, Any]:
    data = asdict(verdict)
    data["known_impls"] = [
        _type_name(impl) if isinstance(impl, type) else str(impl)
        for impl in verdict.known_impls
    ]
    if verdict.status is not None:
        data["status"] = verdict.status.value
    return data


@dataclass(frozen=True)
class AnalysisReport:
    verdicts: list[ClosureVerdict]
    confidence: float
    metadata: dict[str, Any] | None = None
    errors: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "verdicts": [_verdict_to_dict(verdict) for verdict in self.verdicts],
            "metadata": self.metadata or {},
            "errors": self.errors or [],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def to_html(self) -> str:
        rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(verdict.method_qualname)}</td>"
            f"<td>{html.escape(verdict.signal)}</td>"
            f"<td>{html.escape(verdict.rationale)}</td>"
            "</tr>"
            for verdict in self.verdicts
        )
        return (
            "<html><body>"
            f"<p>Confidence: {self.confidence:.2f}</p>"
            "<table><thead><tr><th>Method</th><th>Signal</th>"
            "<th>Rationale</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            "</body></html>"
        )


def evaluation_metrics_to_html(metrics: EvaluationMetrics) -> str:
    rows = []
    payload = metrics.to_json()
    for key, value in payload["counts"].items():
        rows.append(f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>")
    for key in ("precision", "recall", "false_positive_rate", "false_negative_rate"):
        rows.append(f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(payload[key]))}</td></tr>")
    return (
        "<html><body><h1>flatten evidence report</h1>"
        "<table>"
        + "".join(rows)
        + "</table></body></html>"
    )
