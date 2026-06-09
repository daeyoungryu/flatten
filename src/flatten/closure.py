"""닫힌/열린 계층 판정 (OS1~OS5 신호 검사)."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any


@dataclass
class ClosureVerdict:
    method_qualname: str
    is_closed: bool
    known_impls: list[type]
    open_signals: list[str] = field(default_factory=list)


def _all_subclasses(cls: type) -> list[type]:
    result: list[type] = []
    queue = list(cls.__subclasses__())
    while queue:
        sub = queue.pop()
        result.append(sub)
        queue.extend(sub.__subclasses__())
    return result


def _check_os1(cls: type, subs: list[type]) -> str | None:
    """OS1: 모듈 경계 밖 상속 — 외부 모듈에서 온 서브클래스 존재."""
    base_module = getattr(sys.modules.get(cls.__module__), "__name__", cls.__module__)
    for sub in subs:
        if not sub.__module__.startswith(base_module.split(".")[0]):
            return f"OS1: external subclass {sub.__qualname__} from {sub.__module__}"
    return None


def _check_os2(cls: type) -> str | None:
    """OS2: 동적 클래스 생성 — type() 또는 types.new_class 사용 흔적."""
    for sub in _all_subclasses(cls):
        if sub.__qualname__.endswith("<locals>.<class>") or "<locals>" in sub.__qualname__:
            return f"OS2: dynamically created subclass {sub.__qualname__}"
    return None


def _check_os3(cls: type, method_name: str) -> str | None:
    """OS3: 덕타이핑 — ABC 없이 같은 이름 메서드만 공유."""
    import abc
    if not issubclass(cls, abc.ABC) and not getattr(cls, "__abstractmethods__", None):
        # 모든 서브클래스가 같은 메서드를 독립적으로 정의했는지 확인
        defining_classes = [s for s in _all_subclasses(cls) if method_name in s.__dict__]
        if len(defining_classes) > 1 and method_name not in cls.__dict__:
            return f"OS3: duck-typed method '{method_name}' without ABC"
    return None


def _check_os4(cls: type) -> str | None:
    """OS4: __getattr__ / __getattribute__ 오버라이드."""
    for klass in [cls] + _all_subclasses(cls):
        if "__getattr__" in klass.__dict__ or "__getattribute__" in klass.__dict__:
            return f"OS4: {klass.__qualname__} overrides __getattr__/__getattribute__"
    return None


def _check_os5(cls: type) -> str | None:
    """OS5: 조건부 클래스 정의 — if 블록 안에 class 정의."""
    try:
        source = inspect.getsource(cls)
        # 간단한 휴리스틱: 소스에 조건 분기가 포함된 경우
        if "\nif " in source and "\nclass " in source:
            return f"OS5: conditional class definition detected in {cls.__qualname__}"
    except (OSError, TypeError):
        pass
    return None


class ClosureChecker:
    def check(self, method_qualname: str, observed_impls: list[type]) -> ClosureVerdict:
        if not observed_impls:
            return ClosureVerdict(method_qualname, False, [], ["no observed impls"])

        base_cls = observed_impls[0]
        method_name = method_qualname.rsplit(".", 1)[-1]

        # 메서드를 최초 정의한 클래스를 찾는다
        for cls in observed_impls[0].__mro__:
            if method_name in cls.__dict__:
                base_cls = cls
                break

        all_subs = _all_subclasses(base_cls)
        signals: list[str] = []

        for check in [
            lambda: _check_os1(base_cls, all_subs),
            lambda: _check_os2(base_cls),
            lambda: _check_os3(base_cls, method_name),
            lambda: _check_os4(base_cls),
            lambda: _check_os5(base_cls),
        ]:
            sig = check()
            if sig:
                signals.append(sig)

        is_closed = len(signals) == 0 and set(observed_impls).issuperset(set(all_subs))
        return ClosureVerdict(method_qualname, is_closed, list(observed_impls), signals)
