"""Direct finite-trace interpreter for Warehouse Task Language sources."""

from __future__ import annotations

import operator
from collections.abc import Sequence
from typing import Protocol

from .model import (
    AllOf,
    Alternative,
    Avoid,
    CountAtMost,
    Deadline,
    MaintainUntil,
    On,
    Once,
    Ordered,
    Priority,
    Since,
    Task,
    TaskExpression,
    Threshold,
    Visit,
)
from .parser import parse_task


class TraceStepLike(Protocol):
    propositions: frozenset[str]

    def resource(self, name: str) -> int: ...


_COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def _has(trace: Sequence[TraceStepLike], index: int, event: str) -> bool:
    return 0 <= index < len(trace) and event in trace[index].propositions


def evaluate_expression(
    expression: TaskExpression,
    trace: Sequence[TraceStepLike],
    position: int = 0,
) -> bool:
    """Evaluate an expression on a finite trace suffix beginning at position."""

    if not 0 <= position <= len(trace):
        raise ValueError("position must be between zero and trace length")
    if isinstance(expression, Visit):
        return any(
            _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Avoid):
        return all(
            not _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Ordered):
        cursor = position
        for event in expression.events:
            match = next(
                (
                    index
                    for index in range(cursor, len(trace))
                    if _has(trace, index, event)
                ),
                None,
            )
            if match is None:
                return False
            cursor = match + 1
        return True
    if isinstance(expression, Deadline):
        return any(
            _has(trace, index, expression.event)
            for index in range(
                position + expression.lower,
                min(position + expression.upper + 1, len(trace)),
            )
        )
    if isinstance(expression, MaintainUntil):
        goal = next(
            (
                index
                for index in range(position, len(trace))
                if _has(trace, index, expression.goal)
            ),
            None,
        )
        return goal is not None and all(
            not _has(trace, index, expression.forbidden)
            for index in range(position, goal)
        )
    if isinstance(expression, On):
        return all(
            evaluate_expression(expression.obligation, trace, index)
            for index in range(position, len(trace))
            if _has(trace, index, expression.trigger)
        )
    if isinstance(expression, Alternative):
        return any(
            evaluate_expression(item, trace, position) for item in expression.options
        )
    if isinstance(expression, AllOf):
        return all(
            evaluate_expression(item, trace, position)
            for item in expression.requirements
        )
    if isinstance(expression, CountAtMost):
        occurrences = sum(
            _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
        return occurrences <= expression.maximum
    if isinstance(expression, Once):
        return any(
            _has(trace, index, expression.event)
            for index in range(0, position + 1)
        )
    if isinstance(expression, Since):
        landmarks = [
            index
            for index in range(0, position + 1)
            if _has(trace, index, expression.landmark)
        ]
        return bool(landmarks) and all(
            _has(trace, index, expression.condition)
            for index in range(landmarks[-1], position + 1)
        )
    if isinstance(expression, Threshold):
        compare = _COMPARISONS[expression.operator]
        return all(
            compare(trace[index].resource(expression.resource), expression.value)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Priority):
        return priority_rank(expression, trace, position) is not None
    raise TypeError(f"unsupported WTL expression: {type(expression)!r}")


def priority_rank(
    expression: Priority,
    trace: Sequence[TraceStepLike],
    position: int = 0,
) -> int | None:
    """Return the zero-based rank of the first successful preference."""

    return next(
        (
            rank
            for rank, option in enumerate(expression.options)
            if evaluate_expression(option, trace, position)
        ),
        None,
    )


def requirement_diagnostics(
    task: Task, trace: Sequence[TraceStepLike]
) -> dict[str, bool]:
    """Evaluate each named requirement without changing task acceptance."""

    return {
        requirement.id: evaluate_expression(requirement.expression, trace)
        for requirement in task.requirements
    }


def evaluate_task(source: str, trace: Sequence[TraceStepLike]) -> bool:
    """Parse and evaluate one WTL source against a finite warehouse trace."""

    task = parse_task(source)
    return all(requirement_diagnostics(task, trace).values())
