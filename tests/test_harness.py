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


def test_behavior_hash_uses_value_comparison_not_repr_address():
    class AddressRepr:
        def __repr__(self):
            return f"<AddressRepr at {id(self):x}>"

        def __eq__(self, other):
            return isinstance(other, AddressRepr)

    def make_value():
        return AddressRepr()

    assert compute_behavior_hash(make_value, [((), {})]) == compute_behavior_hash(
        make_value, [((), {})]
    )


def test_assert_equivalent_compares_exceptions_by_type_and_message():
    def original():
        raise ValueError("same")

    def transformed():
        raise ValueError("same")

    assert_equivalent(original, transformed, [((), {})])


def test_assert_equivalent_accepts_custom_equivalence_function():
    def original():
        return {"items": [1, 2]}

    def transformed():
        return {"items": (1, 2)}

    assert_equivalent(
        original,
        transformed,
        [((), {})],
        equivalent=lambda left, right: list(left["items"]) == list(right["items"]),
    )
