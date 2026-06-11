# Architecture

`flatten-polymorph` is a conservative Python dispatch analysis and rewrite
tool. Observation records are evidence, not proof, and the planner rejects
anything that cannot be justified by positive closure evidence.

Pipeline:

1. `discovery.py` finds source-positioned `obj.method(...)` call sites.
2. `tracer.py` records runtime receiver and caller evidence.
3. `observations.py` serializes stable type/function references.
4. `static.py` extracts class hierarchy and dynamic risk signals.
5. `closure.py` returns CLOSED, OPEN, UNSAFE, or UNKNOWN verdicts.
6. `planner.py` emits rewrite decisions and plans only for allowed CLOSED cases.
7. `transformer.py` applies exact LibCST position-based rewrites.
8. `harness.py` verifies observed-input behavior in-process or subprocess.

The implementation package is `flatten`. The distribution name is
`flatten-polymorph`. `flatten_polymorph` is a compatibility import shim.
