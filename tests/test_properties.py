from hypothesis import given
from hypothesis import strategies as st

from flatten.harness import assert_equivalent, compute_behavior_hash


@given(st.lists(st.integers(), max_size=20))
def test_behavior_hash_is_deterministic_for_pure_values(values):
    def fn():
        return list(values)

    inputs = [((), {})]
    assert compute_behavior_hash(fn, inputs) == compute_behavior_hash(fn, inputs)


@given(st.integers())
def test_equivalence_accepts_identity_transform(value):
    assert_equivalent(lambda x: x, lambda x: x, [((value,), {})])
