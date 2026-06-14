import sys

from flatten.comparator import BehaviorComparator


def test_behavior_comparator_reports_equivalent_return_and_streams():
    def left(value):
        print("out")
        print("err", file=sys.stderr)
        return value + 1

    def right(value):
        print("out")
        print("err", file=sys.stderr)
        return value + 1

    result = BehaviorComparator().compare(left, right, [((1,), {})])

    assert result.equivalent is True
    assert result.mismatches == []


def test_behavior_comparator_reports_exception_message_mismatch():
    def left():
        raise ValueError("left")

    def right():
        raise ValueError("right")

    result = BehaviorComparator().compare(left, right, [((), {})])

    assert result.equivalent is False
    assert result.mismatches[0].field == "exception"
    assert "left" in result.mismatches[0].original
    assert "right" in result.mismatches[0].transformed
