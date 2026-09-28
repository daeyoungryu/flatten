import sys
from flatten.comparator import BehaviorComparator


def _orig(x):
    print("o")
    return x


def _tr(x):
    print("o")
    return x if x % 2 == 0 else x + 100


def test_all_case_mismatches_are_kept():
    r = BehaviorComparator().compare(_orig, _tr, [((1,), {}), ((2,), {}), ((3,), {})])
    assert r.equivalent is False
    assert r.cases == 3
    assert [m.case_index for m in r.mismatches] == [0, 2]


def test_mismatch_then_matching_case_is_not_equivalent():
    r = BehaviorComparator().compare(_orig, _tr, [((1,), {}), ((2,), {})])
    assert r.equivalent is False
    assert [m.case_index for m in r.mismatches] == [0]


def test_multiple_fields_in_one_case_and_later_ok_case():
    def left(x):
        print("a")
        return x

    def right(x):
        print("b")
        return x + 1 if x == 1 else x

    r = BehaviorComparator().compare(left, right, [((1,), {}), ((2,), {}), ((3,), {})])
    assert sorted((m.case_index, m.field) for m in r.mismatches) == [(0, "effects"), (0, "return"), (1, "effects"), (2, "effects")]


def test_all_equal_is_equivalent():
    r = BehaviorComparator().compare(_orig, _orig, [((1,), {}), ((2,), {})])
    assert r.equivalent is True and r.mismatches == [] and r.cases == 2
