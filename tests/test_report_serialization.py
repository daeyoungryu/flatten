import json

from flatten.contracts import ClosureVerdict
from flatten.report import AnalysisReport


def test_report_serializes_class_objects_to_stable_names():
    class Impl:
        pass

    report = AnalysisReport(
        [ClosureVerdict("Base.process", False, [Impl], ["OPEN"], "OPEN")],
        confidence=0.5,
    )

    payload = json.loads(report.to_json())

    assert payload["verdicts"][0]["known_impls"] == [
        f"{Impl.__module__}.{Impl.__qualname__}"
    ]
