"""Neutral-task authoring compiler into the frozen A1 formula vocabulary."""

from __future__ import annotations

from functools import reduce

from neutral_ir.schema import (
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

from .syntax import (
    Always,
    And,
    Atom,
    CountAtMostFormula,
    Eventually,
    Formula,
    Implies,
    Next,
    Not,
    OnceFormula,
    Or,
    PriorityFormula,
    ResourceComparison,
    SinceFormula,
    Until,
)


def _next_power(formula: Formula, count: int) -> Formula:
    for _ in range(count):
        formula = Next(formula)
    return formula


def _ordered(events: tuple[str, ...]) -> Formula:
    if not events:
        return And(())
    tail: Formula = Eventually(Atom(events[-1]))
    for event in reversed(events[:-1]):
        tail = Eventually(And((Atom(event), Next(tail))))
    return tail


def compile_expression(expr: Expression) -> Formula:
    if isinstance(expr, Visit):
        return Eventually(Atom(expr.event))
    if isinstance(expr, Avoid):
        return Always(Not(Atom(expr.event)))
    if isinstance(expr, OrderedVisit):
        return _ordered(expr.events)
    if isinstance(expr, Deadline):
        return Or(
            tuple(
                _next_power(Atom(expr.event), offset)
                for offset in range(expr.lower, expr.upper + 1)
            )
        )
    if isinstance(expr, MaintainUntil):
        return Until(Not(Atom(expr.forbidden)), Atom(expr.goal))
    if isinstance(expr, On):
        return Always(Implies(Atom(expr.trigger), compile_expression(expr.obligation)))
    if isinstance(expr, Alternative):
        return Or(tuple(compile_expression(option) for option in expr.options))
    if isinstance(expr, AllOf):
        return And(
            tuple(compile_expression(requirement) for requirement in expr.requirements)
        )
    if isinstance(expr, CountAtMost):
        return CountAtMostFormula(Atom(expr.event), expr.maximum)
    if isinstance(expr, Once):
        return OnceFormula(Atom(expr.event))
    if isinstance(expr, Since):
        return SinceFormula(Atom(expr.condition), Atom(expr.landmark))
    if isinstance(expr, Threshold):
        return Always(ResourceComparison(expr.resource, expr.operator, expr.value))
    if isinstance(expr, Priority):
        return PriorityFormula(
            tuple(compile_expression(option) for option in expr.options)
        )
    raise TypeError(f"Unsupported task primitive: {type(expr)!r}")


def compile_task(task: TaskSpec) -> Formula:
    return And(
        tuple(compile_expression(requirement.expr) for requirement in task.requirements)
    )


def format_formula(formula: Formula) -> str:
    if isinstance(formula, Atom):
        return formula.name
    if isinstance(formula, ResourceComparison):
        return f"RESOURCE[{formula.resource} {formula.operator} {formula.value}]"
    if isinstance(formula, Not):
        return f"!({format_formula(formula.operand)})"
    if isinstance(formula, And):
        return "(" + " & ".join(format_formula(item) for item in formula.operands) + ")"
    if isinstance(formula, Or):
        return "(" + " | ".join(format_formula(item) for item in formula.operands) + ")"
    if isinstance(formula, Next):
        return f"X({format_formula(formula.operand)})"
    if isinstance(formula, Eventually):
        return f"F({format_formula(formula.operand)})"
    if isinstance(formula, Always):
        return f"G({format_formula(formula.operand)})"
    if isinstance(formula, Until):
        return f"({format_formula(formula.left)} U {format_formula(formula.right)})"
    if isinstance(formula, Implies):
        return f"({format_formula(formula.antecedent)} -> {format_formula(formula.consequent)})"
    if isinstance(formula, CountAtMostFormula):
        return f"COUNT_AT_MOST({formula.atom.name}, {formula.maximum})"
    if isinstance(formula, OnceFormula):
        return f"ONCE({formula.atom.name})"
    if isinstance(formula, SinceFormula):
        return f"({formula.condition.name} SINCE {formula.landmark.name})"
    if isinstance(formula, PriorityFormula):
        return (
            "PRIORITY("
            + ", ".join(format_formula(item) for item in formula.options)
            + ")"
        )
    raise TypeError(type(formula))
