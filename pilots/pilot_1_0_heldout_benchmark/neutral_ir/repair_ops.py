"""Fixed Experiment-B repair vocabulary, bounded to search depth four."""

from __future__ import annotations

from dataclasses import replace

from .schema import (
    CountAtMost,
    Deadline,
    OrderedVisit,
    Requirement,
    TaskSpec,
)


def unit_repairs(task: TaskSpec) -> tuple[tuple[str, TaskSpec], ...]:
    repairs: list[tuple[str, TaskSpec]] = []
    for index, requirement in enumerate(task.requirements):
        remaining = task.requirements[:index] + task.requirements[index + 1 :]
        repairs.append(
            (f"remove:{requirement.id}", replace(task, requirements=remaining))
        )
        expr = requirement.expr
        replacements = []
        if isinstance(expr, Deadline):
            replacements.append(
                (f"deadline+1:{requirement.id}", replace(expr, upper=expr.upper + 1))
            )
        if isinstance(expr, OrderedVisit) and len(expr.events) > 1:
            for event_index in range(len(expr.events)):
                events = expr.events[:event_index] + expr.events[event_index + 1 :]
                replacements.append(
                    (
                        f"drop_ordered:{requirement.id}:{event_index}",
                        replace(expr, events=events),
                    )
                )
        if isinstance(expr, CountAtMost):
            replacements.append(
                (f"count+1:{requirement.id}", replace(expr, maximum=expr.maximum + 1))
            )
        for label, new_expr in replacements:
            requirements = list(task.requirements)
            requirements[index] = Requirement(requirement.id, new_expr)
            repairs.append((label, replace(task, requirements=tuple(requirements))))
    return tuple(repairs)
