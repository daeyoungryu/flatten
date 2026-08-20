from flatten.contracts import CallSite
from flatten.planner import EvaluationSafety


def _site(receiver: str, *, line: int = 2, column: int = 11) -> CallSite:
    return CallSite(
        call_site_id=f"case.py:{line}:{column}-{line}:{column + 12}",
        filename="case.py",
        line=line,
        column=column,
        end_line=line,
        end_column=column + len(receiver) + len(".run()"),
        qualified_name=f"{receiver}.run",
        receiver_expr=receiver,
        method_name="run",
    )


def test_alias_only_import_refuses_unbound_generated_class_name() -> None:
    source = "from workers import Worker as W\nresult = obj.run()\n"

    safety = EvaluationSafety(
        _site("obj", column=9), ["workers.Worker", "workers.FastWorker"], source
    )

    assert safety.must_refuse()


def test_local_class_qualname_is_refused() -> None:
    source = "def run(obj):\n    return obj.run()\n"

    safety = EvaluationSafety(
        _site("obj"), ["pkg.make_worker.<locals>.Worker"], source
    )

    assert safety.must_refuse()


def test_guarded_temp_nested_after_side_effect_is_refused() -> None:
    source = "def run(factory):\n    return log() + factory().run()\n"
    site = _site("factory()", column=19)

    safety = EvaluationSafety(site, ["pkg.Base", "pkg.Child"], source)

    assert safety.must_refuse()


def test_guarded_temp_whole_return_value_preserves_order() -> None:
    source = "def run(factory):\n    return factory().run()\n"

    safety = EvaluationSafety(
        _site("factory()"), ["pkg.Base", "pkg.Child"], source
    )

    assert not safety.must_refuse()
