import sys
sys.path.insert(0, "src")
from flatten.harness import capture_behavior
calls = []
state = {"n": 0}
def a(): calls.append("a"); return 1
def b():
    calls.append("b"); state["n"] += 1
    if state["n"] == 1: raise ValueError("flaky")
    return 2
o = capture_behavior(lambda: 5, effect_collectors={"a": a, "b": b})
print("outcome=%s type=%s calls=%s effects=%s" % (o.outcome, o.exception_type, calls, o.effects))
