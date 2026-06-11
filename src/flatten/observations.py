"""Runtime observation records linked to static call-site identifiers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TypeRef:
    module: str
    qualname: str
    file: str | None
    is_builtin: bool

    @property
    def dotted(self) -> str:
        return f"{self.module}.{self.qualname}" if self.module else self.qualname


@dataclass(frozen=True)
class FunctionRef:
    module: str
    qualname: str
    file: str | None
    firstlineno: int | None

    @property
    def dotted(self) -> str:
        return f"{self.module}.{self.qualname}" if self.module else self.qualname


@dataclass(frozen=True)
class ObservationRecord:
    call_site_id: str
    receiver_type: TypeRef | str
    resolved_function: FunctionRef | str
    method_name: str = ""
    frame_module: str = ""
    order: int = 0
    input_hash: str = ""
    module: str = ""
    qualname: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _type_ref_from_any(value: Any) -> TypeRef | str:
    if isinstance(value, dict):
        return TypeRef(
            module=str(value.get("module", "")),
            qualname=str(value.get("qualname", "")),
            file=None if value.get("file") is None else str(value.get("file")),
            is_builtin=bool(value.get("is_builtin", False)),
        )
    return str(value)


def _function_ref_from_any(value: Any) -> FunctionRef | str:
    if isinstance(value, dict):
        firstlineno = value.get("firstlineno")
        return FunctionRef(
            module=str(value.get("module", "")),
            qualname=str(value.get("qualname", "")),
            file=None if value.get("file") is None else str(value.get("file")),
            firstlineno=None if firstlineno is None else int(firstlineno),
        )
    return str(value)


def observations_from_json(payload: str) -> list[ObservationRecord]:
    raw = json.loads(payload)
    if not isinstance(raw, list):
        raise ValueError("observation payload must be a JSON list")
    records: list[ObservationRecord] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"observation #{index} must be an object")
        missing = {
            "call_site_id",
            "receiver_type",
            "resolved_function",
        } - set(item)
        if missing:
            raise ValueError(f"observation #{index} missing fields: {sorted(missing)}")
        resolved = _function_ref_from_any(item["resolved_function"])
        records.append(
            ObservationRecord(
                call_site_id=str(item["call_site_id"]).replace("\\", "/"),
                receiver_type=_type_ref_from_any(item["receiver_type"]),
                resolved_function=resolved,
                method_name=str(item.get("method_name", "")),
                frame_module=str(item.get("frame_module", "")),
                order=int(item.get("order", 0)),
                input_hash=str(item.get("input_hash", "")),
                module=str(item.get("module", "")),
                qualname=str(item.get("qualname", "")),
            )
        )
    return records


def observations_to_json(records: list[ObservationRecord]) -> str:
    return json.dumps([record.to_dict() for record in records], indent=2, sort_keys=True)


def type_name(value: Any) -> str:
    cls = value if isinstance(value, type) else type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def type_ref(value: Any) -> TypeRef:
    cls = value if isinstance(value, type) else type(value)
    return TypeRef(
        module=cls.__module__,
        qualname=cls.__qualname__,
        file=getattr(__import__(cls.__module__, fromlist=["__file__"]), "__file__", None)
        if cls.__module__ != "builtins"
        else None,
        is_builtin=cls.__module__ == "builtins",
    )


def function_ref(func: Any) -> FunctionRef:
    return FunctionRef(
        module=getattr(func, "__module__", ""),
        qualname=getattr(func, "__qualname__", getattr(func, "__name__", "")),
        file=getattr(getattr(func, "__code__", None), "co_filename", None),
        firstlineno=getattr(getattr(func, "__code__", None), "co_firstlineno", None),
    )


def observation_type_name(record: ObservationRecord) -> str:
    if isinstance(record.receiver_type, TypeRef):
        return record.receiver_type.dotted
    return record.receiver_type


def observation_function_name(record: ObservationRecord) -> str:
    if isinstance(record.resolved_function, FunctionRef):
        return record.resolved_function.dotted
    return record.resolved_function
