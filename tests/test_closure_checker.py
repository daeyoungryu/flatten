from flatten.closure import ClosureChecker


def test_sibling_subclass_gap_is_reported_when_only_one_override_is_observed():
    class Base:
        def process(self):
            return "base"

    class A(Base):
        def process(self):
            return "a"

    class B(Base):
        def process(self):
            return "b"

    verdict = ClosureChecker().check("Base.process", [A])

    assert any("B" in signal for signal in verdict.open_signals)
    assert any(signal.startswith("OS5") for signal in verdict.open_signals)
