import importlib.util
import subprocess
import sys
import time
from typing import final

import pytest

# --- helpers ---------------------------------------------------------------

FIXTURE = '''\
from typing import final

class Animal:                 # OPEN base: not final, not sealed
    def speak(self):
        return "generic"

@final
class Dog(Animal):            # single observed impl, final leaf
    def speak(self):
        return "woof"

class Cat(Animal):            # sibling, visible in the SAME module
    def speak(self):
        return "meow"

def compute(animal):
    return animal.speak()

def main():
    return compute(Dog())
'''


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cli(args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "flatten", *args],
        cwd=str(cwd), capture_output=True, text=True,
    )


# --- P0: SOUNDNESS ---------------------------------------------------------

def test_p0_rewrite_preserves_behavior_on_unobserved_sibling(tmp_path):
    """기본 파이프라인이 형제 타입(Cat) 입력에서 동작을 바꾸면 안 된다.
    현재(v0.1.2): compute(Cat()) 원본 'meow' -> 재작성 'woof' (RED)."""
    src = tmp_path / "zoofix.py"
    src.write_text(FIXTURE)
    obs, plan, rew = tmp_path / "obs.json", tmp_path / "plan.json", tmp_path / "rew.py"

    r = _cli(["trace", "zoofix.py", "--entry", "zoofix:main", "--out", str(obs)], tmp_path)
    assert r.returncode == 0
    r = _cli(["plan", "zoofix.py", "--observations", str(obs), "--out", str(plan)], tmp_path)
    assert r.returncode == 0
    r = _cli(["rewrite", "zoofix.py", "--plan", str(plan), "--out", str(rew),
              "--apply", "--skip-verify"], tmp_path)
    assert r.returncode == 0

    orig = _load("zoo_orig", src)
    rewr = _load("zoo_rew", rew)
    # 불변식: 재작성은 관측 타입뿐 아니라 base의 모든 서브클래스에서 동작 보존.
    assert orig.compute(orig.Cat()) == "meow"
    assert rewr.compute(rewr.Cat()) == "meow"


def test_p0_single_final_leaf_under_open_base_is_not_closed():
    """단일 final 리프만 관측 + open 베이스(형제 존재) => CLOSED 금지.
    파이프라인은 리프 qualname('Dog.speak')으로 check를 호출한다."""
    from flatten.closure import ClosureChecker, ClosureConfig
    from flatten.contracts import ClosureStatus

    class Animal:
        def speak(self): return "generic"

    @final
    class Dog(Animal):
        def speak(self): return "woof"

    class Cat(Animal):            # noqa: F841  형제 존재 => base는 open
        def speak(self): return "meow"

    verdict = ClosureChecker(ClosureConfig()).check("Dog.speak", [Dog])
    assert verdict.status is not ClosureStatus.CLOSED, f"unexpected CLOSED: {verdict.signal}"


# --- P1: TRACER EXCEPTION PATH --------------------------------------------

def test_p1_exception_path_is_observed():
    """예외를 던지는 메서드도 관측되어야 한다. 현재 records==0 (RED)."""
    from flatten.tracer import Tracer

    def raises(x):
        raise ValueError("boom")

    tr = Tracer(raises)
    tr.start()
    with pytest.raises(ValueError):
        raises(1)
    tr.stop()
    assert len(tr.records) == 1, "exception-path observation lost"


# --- P1: TRACER OVERHEAD ---------------------------------------------------

def test_p1_tracer_overhead_is_bounded():
    """트레이서 호출당 오버헤드 상한. 현재 ~400us/call (RED).
    임계값은 환경에 맞게 조정 가능하나 자릿수(10us대)는 유지."""
    from flatten.tracer import Tracer

    def work(x):
        return x + 1

    N = 50_000
    tr = Tracer(work, capture_values=False)
    tr.start()
    t0 = time.perf_counter()
    for i in range(N):
        work(i)
    tr.stop()
    per_call_us = (time.perf_counter() - t0) / N * 1e6
    assert len(tr.records) == N
    assert per_call_us < 25.0, f"tracer overhead {per_call_us:.1f} us/call"
