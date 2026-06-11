from typing import final

from flatten.closure import ClosureChecker
from flatten.contracts import ClosureStatus
from flatten.planner import RewritePlanner


def test_custom_setattr_blocks_rewrite_decision():
    @final
    class DynamicState:
        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

        def run(self):
            return 1

    verdict = ClosureChecker().check("DynamicState.run", [DynamicState])
    decision = RewritePlanner(opt_in=True).decide([verdict])[0]

    assert verdict.status is ClosureStatus.UNSAFE
    assert decision.allowed is False
    assert any("__setattr__" in blocker for blocker in decision.blockers)


def test_init_subclass_hook_blocks_rewrite_even_when_observed_class_is_final():
    class RegistryBase:
        def __init_subclass__(cls):
            super().__init_subclass__()

        def run(self):
            return "base"

    @final
    class Registered(RegistryBase):
        def run(self):
            return "registered"

    verdict = ClosureChecker().check("RegistryBase.run", [Registered])

    assert verdict.status is ClosureStatus.UNSAFE
    assert any("__init_subclass__" in blocker for blocker in verdict.blockers)


def test_dynamic_code_execution_in_observed_method_blocks_rewrite():
    @final
    class Evaluator:
        def run(self, expression):
            return eval(expression)

    verdict = ClosureChecker().check("Evaluator.run", [Evaluator])

    assert verdict.status is ClosureStatus.UNSAFE
    assert any("dynamic code execution" in blocker for blocker in verdict.blockers)


def test_dynamic_import_in_observed_method_blocks_rewrite():
    @final
    class Importer:
        def run(self):
            import math

            return math.sqrt(4)

    verdict = ClosureChecker().check("Importer.run", [Importer])

    assert verdict.status is ClosureStatus.UNSAFE
    assert any("dynamic import" in blocker for blocker in verdict.blockers)
