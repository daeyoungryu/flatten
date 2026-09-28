import pytest
from flatten.comparator import BehaviorComparator


def _orig(x):
    return x


def _bad(x):  # always differs in return
    return x + 1


def _bad2(x):  # differs in return AND effects
    print("x")
    return x + 1


CASES = [((i,), {}) for i in range(5)]


def test_default_none_is_unchanged():
    r = BehaviorComparator().compare(_orig, _bad, CASES)
    assert len(r.mismatches) == 5 and r.cases == 5 and r.truncated is False
    assert r.to_json()["truncated"] is False


def test_stops_when_limit_reached_and_reports_truncated():
    r = BehaviorComparator().compare(_orig, _bad, CASES, max_mismatches=2)
    assert [m.case_index for m in r.mismatches] == [0, 1]
    assert r.cases == 5
    assert r.truncated is True and r.equivalent is False
    assert r.to_json()["truncated"] is True
    assert r.to_json()["cases"] == 5


def test_limit_reached_on_last_case_is_not_truncated():
    r = BehaviorComparator().compare(_orig, _bad, CASES[:2], max_mismatches=2)
    assert len(r.mismatches) == 2 and r.truncated is False


def test_single_case_keeps_all_its_mismatches():
    r = BehaviorComparator().compare(_orig, _bad2, CASES, max_mismatches=1)
    assert [m.case_index for m in r.mismatches] == [0, 0]
    assert sorted(m.field for m in r.mismatches) == ["effects", "return"]
    assert r.truncated is True


def test_limit_larger_than_mismatches_never_truncates():
    r = BehaviorComparator().compare(_orig, _bad, CASES, max_mismatches=99)
    assert len(r.mismatches) == 5 and r.truncated is False


@pytest.mark.parametrize("bad", [0, -1])
def test_invalid_limit_raises(bad):
    with pytest.raises(ValueError):
        BehaviorComparator().compare(_orig, _bad, CASES, max_mismatches=bad)


def test_max_mismatches_is_keyword_only():
    with pytest.raises(TypeError):
        BehaviorComparator().compare(_orig, _bad, CASES, 2)


def test_equivalent_callables_never_truncate():
    r = BehaviorComparator().compare(_orig, _orig, CASES, max_mismatches=1)
    assert r.equivalent is True and r.truncated is False and r.mismatches == []
