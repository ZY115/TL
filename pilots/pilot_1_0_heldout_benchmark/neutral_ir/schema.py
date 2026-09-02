"""Typed Neutral Task IR with canonical JSON serialization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path
from typing import TypeAlias


class Expr:
    """Marker base class for task-semantic nodes, not logical operators."""


@dataclass(frozen=True, slots=True)
class Visit(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Avoid(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class OrderedVisit(Expr):
    events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Deadline(Expr):
    event: str
    lower: int
    upper: int


@dataclass(frozen=True, slots=True)
class MaintainUntil(Expr):
    forbidden: str
    goal: str


@dataclass(frozen=True, slots=True)
class On(Expr):
    trigger: str
    obligation: Expr


@dataclass(frozen=True, slots=True)
class Alternative(Expr):
    options: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class AllOf(Expr):
    requirements: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class CountAtMost(Expr):
    event: str
    maximum: int


@dataclass(frozen=True, slots=True)
class Once(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Since(Expr):
    condition: str
    landmark: str


@dataclass(frozen=True, slots=True)
class Threshold(Expr):
    resource: str
    operator: str
    value: int


@dataclass(frozen=True, slots=True)
class Priority(Expr):
    options: tuple[Expr, ...]


Expression: TypeAlias = (
    Visit
    | Avoid
    | OrderedVisit
    | Deadline
    | MaintainUntil
    | On
    | Alternative
    | AllOf
    | CountAtMost
    | Once
    | Since
    | Threshold
    | Priority
)


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    expr: Expression


@dataclass(frozen=True, slots=True)
class TaskSpec:
    id: str
    requirements: tuple[Requirement, ...]


EXPRESSION_TYPES = {
    cls.__name__: cls
    for cls in (
        Visit,
        Avoid,
        OrderedVisit,
        Deadline,
        MaintainUntil,
        On,
        Alternative,
        AllOf,
        CountAtMost,
        Once,
        Since,
        Threshold,
        Priority,
    )
}


def expr_to_dict(expr: Expression) -> dict[str, object]:
    result: dict[str, object] = {"type": type(expr).__name__}
    for field in fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, Expr):
            result[field.name] = expr_to_dict(value)  # type: ignore[arg-type]
        elif isinstance(value, tuple) and value and isinstance(value[0], Expr):
            result[field.name] = [expr_to_dict(item) for item in value]
        elif isinstance(value, tuple):
            result[field.name] = list(value)
        else:
            result[field.name] = value
    return result


def expr_from_dict(source: dict[str, object]) -> Expression:
    node_type = str(source["type"])
    if node_type not in EXPRESSION_TYPES:
        raise ValueError(f"Unknown Neutral IR node: {node_type}")
    cls = EXPRESSION_TYPES[node_type]
    values: dict[str, object] = {}
    for field in fields(cls):
        value = source[field.name]
        if isinstance(value, dict) and "type" in value:
            values[field.name] = expr_from_dict(value)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            values[field.name] = tuple(expr_from_dict(item) for item in value)
        elif isinstance(value, list):
            values[field.name] = tuple(value)
        else:
            values[field.name] = value
    return cls(**values)  # type: ignore[arg-type,return-value]


def task_to_dict(task: TaskSpec) -> dict[str, object]:
    return {
        "id": task.id,
        "requirements": [
            {"id": requirement.id, "expr": expr_to_dict(requirement.expr)}
            for requirement in task.requirements
        ],
    }


def task_from_dict(source: dict[str, object]) -> TaskSpec:
    requirements = tuple(
        Requirement(str(item["id"]), expr_from_dict(item["expr"]))
        for item in source["requirements"]  # type: ignore[index,union-attr]
    )
    return TaskSpec(str(source["id"]), requirements)


def write_task(path: Path, task: TaskSpec) -> None:
    path.write_text(
        json.dumps(task_to_dict(task), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_task(path: Path) -> TaskSpec:
    return task_from_dict(json.loads(path.read_text(encoding="utf-8")))
