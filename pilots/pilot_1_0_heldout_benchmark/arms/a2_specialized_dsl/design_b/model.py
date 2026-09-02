"""Immutable abstract syntax for the Warehouse Task Language (WTL).

Design seed: 2202.  The nodes are task concepts rather than temporal-logic
operators.  Validation lives here so programmatically built tasks and parsed
tasks obey the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


class Expression:
    """Marker base class for WTL task expressions."""


def _name(value: str, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Visit(Expression):
    event: str

    def __post_init__(self) -> None:
        _name(self.event, "event")


@dataclass(frozen=True, slots=True)
class Avoid(Expression):
    event: str

    def __post_init__(self) -> None:
        _name(self.event, "event")


@dataclass(frozen=True, slots=True)
class Ordered(Expression):
    events: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("ordered requires at least one event")
        for event in self.events:
            _name(event, "event")


@dataclass(frozen=True, slots=True)
class Deadline(Expression):
    event: str
    lower: int
    upper: int

    def __post_init__(self) -> None:
        _name(self.event, "event")
        if self.lower < 0 or self.upper < self.lower:
            raise ValueError("deadline requires 0 <= lower <= upper")


@dataclass(frozen=True, slots=True)
class MaintainUntil(Expression):
    forbidden: str
    goal: str

    def __post_init__(self) -> None:
        _name(self.forbidden, "forbidden")
        _name(self.goal, "goal")


@dataclass(frozen=True, slots=True)
class On(Expression):
    trigger: str
    obligation: Expression

    def __post_init__(self) -> None:
        _name(self.trigger, "trigger")
        if not isinstance(self.obligation, Expression):
            raise TypeError("obligation must be a WTL expression")


@dataclass(frozen=True, slots=True)
class Alternative(Expression):
    options: tuple[Expression, ...]

    def __post_init__(self) -> None:
        _expressions(self.options, "alternative")


@dataclass(frozen=True, slots=True)
class AllOf(Expression):
    requirements: tuple[Expression, ...]

    def __post_init__(self) -> None:
        _expressions(self.requirements, "all_of")


@dataclass(frozen=True, slots=True)
class CountAtMost(Expression):
    event: str
    maximum: int

    def __post_init__(self) -> None:
        _name(self.event, "event")
        if self.maximum < 0:
            raise ValueError("count_at_most maximum must be non-negative")


@dataclass(frozen=True, slots=True)
class Once(Expression):
    event: str

    def __post_init__(self) -> None:
        _name(self.event, "event")


@dataclass(frozen=True, slots=True)
class Since(Expression):
    condition: str
    landmark: str

    def __post_init__(self) -> None:
        _name(self.condition, "condition")
        _name(self.landmark, "landmark")


COMPARISON_OPERATORS = frozenset({"<", "<=", "==", ">=", ">"})


@dataclass(frozen=True, slots=True)
class Threshold(Expression):
    resource: str
    operator: str
    value: int

    def __post_init__(self) -> None:
        _name(self.resource, "resource")
        if self.operator not in COMPARISON_OPERATORS:
            raise ValueError(f"unsupported threshold operator: {self.operator}")


@dataclass(frozen=True, slots=True)
class Priority(Expression):
    options: tuple[Expression, ...]

    def __post_init__(self) -> None:
        _expressions(self.options, "priority")


def _expressions(values: tuple[Expression, ...], construct: str) -> None:
    if not values:
        raise ValueError(f"{construct} requires at least one expression")
    if not all(isinstance(value, Expression) for value in values):
        raise TypeError(f"{construct} accepts only WTL expressions")


TaskExpression: TypeAlias = (
    Visit
    | Avoid
    | Ordered
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
    expression: TaskExpression

    def __post_init__(self) -> None:
        _name(self.id, "requirement id")
        if not isinstance(self.expression, Expression):
            raise TypeError("requirement expression must be a WTL expression")


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    requirements: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        _name(self.id, "task id")
        if not self.requirements:
            raise ValueError("task requires at least one requirement")
        ids = [requirement.id for requirement in self.requirements]
        if len(set(ids)) != len(ids):
            raise ValueError("requirement ids must be unique within a task")
