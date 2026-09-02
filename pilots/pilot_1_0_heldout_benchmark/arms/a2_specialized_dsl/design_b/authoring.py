"""Deterministic, information-preserving Neutral Task IR to WTL authoring."""

from __future__ import annotations

from neutral_ir.schema import (
    AllOf as IRAllOf,
    Alternative as IRAlternative,
    Avoid as IRAvoid,
    CountAtMost as IRCountAtMost,
    Deadline as IRDeadline,
    Expression as IRExpression,
    MaintainUntil as IRMaintainUntil,
    On as IROn,
    Once as IROnce,
    OrderedVisit as IROrderedVisit,
    Priority as IRPriority,
    Since as IRSince,
    TaskSpec,
    Threshold as IRThreshold,
    Visit as IRVisit,
)

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
    Requirement,
    Since,
    Task,
    TaskExpression,
    Threshold,
    Visit,
)
from .parser import format_task


def expression_from_ir(expression: IRExpression) -> TaskExpression:
    """Translate every supported Neutral IR field to an explicit WTL node."""

    if isinstance(expression, IRVisit):
        return Visit(expression.event)
    if isinstance(expression, IRAvoid):
        return Avoid(expression.event)
    if isinstance(expression, IROrderedVisit):
        return Ordered(expression.events)
    if isinstance(expression, IRDeadline):
        return Deadline(expression.event, expression.lower, expression.upper)
    if isinstance(expression, IRMaintainUntil):
        return MaintainUntil(expression.forbidden, expression.goal)
    if isinstance(expression, IROn):
        return On(expression.trigger, expression_from_ir(expression.obligation))
    if isinstance(expression, IRAlternative):
        return Alternative(tuple(expression_from_ir(item) for item in expression.options))
    if isinstance(expression, IRAllOf):
        return AllOf(
            tuple(expression_from_ir(item) for item in expression.requirements)
        )
    if isinstance(expression, IRCountAtMost):
        return CountAtMost(expression.event, expression.maximum)
    if isinstance(expression, IROnce):
        return Once(expression.event)
    if isinstance(expression, IRSince):
        return Since(expression.condition, expression.landmark)
    if isinstance(expression, IRThreshold):
        return Threshold(expression.resource, expression.operator, expression.value)
    if isinstance(expression, IRPriority):
        return Priority(tuple(expression_from_ir(item) for item in expression.options))
    raise TypeError(f"unsupported Neutral IR expression: {type(expression)!r}")


def task_from_ir(task: TaskSpec) -> Task:
    """Build the corresponding immutable WTL syntax tree."""

    if not isinstance(task, TaskSpec):
        raise TypeError("task must be a neutral_ir.schema.TaskSpec")
    return Task(
        task.id,
        tuple(
            Requirement(item.id, expression_from_ir(item.expr))
            for item in task.requirements
        ),
    )


def encode_task(task: TaskSpec) -> str:
    """Encode a Neutral Task IR value as canonical, self-contained WTL source."""

    return format_task(task_from_ir(task))
