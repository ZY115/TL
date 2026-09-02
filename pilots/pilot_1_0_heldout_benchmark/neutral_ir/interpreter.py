"""Direct mathematical finite-trace interpreter for the Neutral Task IR."""

from __future__ import annotations

import operator
from collections.abc import Sequence

from environments.warehouse import TraceStep

from .schema import (
    AllOf,
    Alternative,
    Avoid,
    CountAtMost,
    Deadline,
    Expression,
    MaintainUntil,
    On,
    Once,
    OrderedVisit,
    Priority,
    Since,
    TaskSpec,
    Threshold,
    Visit,
)

COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def _has(trace: Sequence[TraceStep], index: int, event: str) -> bool:
    return 0 <= index < len(trace) and event in trace[index].propositions


def evaluate_expression(
    expr: Expression, trace: Sequence[TraceStep], position: int = 0
) -> bool:
    if isinstance(expr, Visit):
        return any(
            _has(trace, index, expr.event) for index in range(position, len(trace))
        )
    if isinstance(expr, Avoid):
        return all(
            not _has(trace, index, expr.event) for index in range(position, len(trace))
        )
    if isinstance(expr, OrderedVisit):
        cursor = position
        for event in expr.events:
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
    if isinstance(expr, Deadline):
        return any(
            _has(trace, index, expr.event)
            for index in range(
                position + expr.lower, min(position + expr.upper + 1, len(trace))
            )
        )
    if isinstance(expr, MaintainUntil):
        goal = next(
            (
                index
                for index in range(position, len(trace))
                if _has(trace, index, expr.goal)
            ),
            None,
        )
        return goal is not None and all(
            not _has(trace, index, expr.forbidden) for index in range(position, goal)
        )
    if isinstance(expr, On):
        return all(
            evaluate_expression(expr.obligation, trace, index)
            for index in range(position, len(trace))
            if _has(trace, index, expr.trigger)
        )
    if isinstance(expr, Alternative):
        return any(evaluate_expression(item, trace, position) for item in expr.options)
    if isinstance(expr, AllOf):
        return all(
            evaluate_expression(item, trace, position) for item in expr.requirements
        )
    if isinstance(expr, CountAtMost):
        return (
            sum(_has(trace, index, expr.event) for index in range(position, len(trace)))
            <= expr.maximum
        )
    if isinstance(expr, Once):
        return any(_has(trace, index, expr.event) for index in range(0, position + 1))
    if isinstance(expr, Since):
        landmarks = [
            index
            for index in range(0, position + 1)
            if _has(trace, index, expr.landmark)
        ]
        return bool(landmarks) and all(
            _has(trace, index, expr.condition)
            for index in range(landmarks[-1], position + 1)
        )
    if isinstance(expr, Threshold):
        if expr.operator not in COMPARISONS:
            raise ValueError(f"Unsupported threshold operator: {expr.operator}")
        compare = COMPARISONS[expr.operator]
        return all(
            compare(trace[index].resource(expr.resource), expr.value)
            for index in range(position, len(trace))
        )
    if isinstance(expr, Priority):
        # Boolean acceptance means at least one ranked option succeeds. Preference
        # rank is exposed separately; Priority is not reduced to a trace-logic op.
        return any(evaluate_expression(item, trace, position) for item in expr.options)
    raise TypeError(f"Unsupported Neutral IR node: {type(expr)!r}")


def priority_rank(
    expr: Priority, trace: Sequence[TraceStep], position: int = 0
) -> int | None:
    return next(
        (
            index
            for index, option in enumerate(expr.options)
            if evaluate_expression(option, trace, position)
        ),
        None,
    )


def requirement_diagnostics(
    task: TaskSpec, trace: Sequence[TraceStep]
) -> dict[str, bool]:
    return {
        requirement.id: evaluate_expression(requirement.expr, trace)
        for requirement in task.requirements
    }


def evaluate_ir(task: TaskSpec, trace: Sequence[TraceStep]) -> bool:
    return all(requirement_diagnostics(task, trace).values())
