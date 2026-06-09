import pytest

from flatten.harness import assert_equivalent, compute_behavior_hash


def test_compute_behavior_hash_is_stable_for_same_behavior():
    def left(value):
        print(f"value={value}")
        return value * 2

    def right(value):
        print(f"value={value}")
        return value * 2

    inputs = [((3,), {}), ((5,), {})]
    assert compute_behavior_hash(left, inputs) == compute_behavior_hash(right, inputs)


def test_assert_equivalent_passes_for_matching_behavior():
    def original(value):
        print("same")
        return value + 1

    def transformed(value):
        print("same")
        return value + 1

    assert_equivalent(original, transformed, [((2,), {})])


def test_assert_equivalent_reports_return_divergence_detail():
    def original(value):
        return value + 1

    def transformed(value):
        return value + 2

    with pytest.raises(AssertionError, match="input #0.*original.*transformed"):
        assert_equivalent(original, transformed, [((2,), {})])


def test_assert_equivalent_reports_side_effect_divergence_detail():
    def original():
        print("left")

    def transformed():
        print("right")

    with pytest.raises(AssertionError, match="stdout.*left.*right"):
        assert_equivalent(original, transformed, [((), {})])
