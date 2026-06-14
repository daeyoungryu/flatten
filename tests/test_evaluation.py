from flatten.contracts import ClosureStatus, RewriteDecision
from flatten.discovery import discover_call_sites
from flatten.evaluation import (
    EvaluationCounts,
    LabeledOutcome,
    compute_metrics,
    evaluate_artifacts,
)


def test_evaluation_counts_derive_rates_from_labeled_outcomes():
    counts = EvaluationCounts(
        total_call_sites=5,
        candidate_call_sites=4,
        rewritten_call_sites=2,
        rejected_call_sites=2,
        unsafe_call_sites=1,
        unknown_call_sites=1,
    )
    outcomes = [
        LabeledOutcome(expected_safe=True, rewritten=True),
        LabeledOutcome(expected_safe=True, rewritten=False),
        LabeledOutcome(expected_safe=False, rewritten=True),
        LabeledOutcome(expected_safe=False, rewritten=False),
    ]

    metrics = compute_metrics(counts, outcomes)

    assert metrics.counts == counts
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.false_negative_rate == 0.5


def test_evaluation_metrics_json_is_stable():
    counts = EvaluationCounts(
        total_call_sites=1,
        candidate_call_sites=1,
        rewritten_call_sites=0,
        rejected_call_sites=1,
        unsafe_call_sites=0,
        unknown_call_sites=1,
    )

    payload = compute_metrics(counts, []).to_json()

    assert payload["counts"]["total_call_sites"] == 1
    assert payload["precision"] is None
    assert payload["recall"] is None
    assert payload["false_positive_rate"] is None
    assert payload["false_negative_rate"] is None


def test_evaluate_artifacts_counts_call_sites_and_decisions():
    source = """
class A:
    def run(self):
        return 1

def main(a):
    return a.run()
"""
    call_sites = discover_call_sites(source, filename="case.py")
    decisions = [
        RewriteDecision(
            method_qualname="A.run",
            allowed=False,
            status=ClosureStatus.UNSAFE,
            blockers=("UNSAFE: monkey patch",),
            reason_code="UNSAFE_MONKEY_PATCH",
        )
    ]

    result = evaluate_artifacts(call_sites, decisions)

    assert result.counts.total_call_sites == 1
    assert result.counts.candidate_call_sites == 1
    assert result.counts.rewritten_call_sites == 0
    assert result.counts.rejected_call_sites == 1
    assert result.counts.unsafe_call_sites == 1
    assert result.counts.unknown_call_sites == 0
