"""JSON and HTML reporting for flatten analysis."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from typing import Any

from flatten.contracts import ClosureVerdict


@dataclass(frozen=True)
class AnalysisReport:
    verdicts: list[ClosureVerdict]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "verdicts": [asdict(verdict) for verdict in self.verdicts],
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
