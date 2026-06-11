from flatten.evaluation import EvaluationCounts, LabeledOutcome, compute_metrics


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
