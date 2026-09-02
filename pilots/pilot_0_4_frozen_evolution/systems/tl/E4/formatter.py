"""Deterministic Core-TL formatter with strong Until support."""

from __future__ import annotations

from .syntax import (
    Always,
    And,
    Atom,
    BoundedEventually,
    Eventually,
    Formula,
    Implies,
    Not,
    Or,
    Until,
)


def format_formula(formula: Formula) -> str:
    if isinstance(formula, Atom):
        return formula.name
    if isinstance(formula, Not):
        return f"!({format_formula(formula.operand)})"
    if isinstance(formula, And):
        return f"({format_formula(formula.left)} & {format_formula(formula.right)})"
    if isinstance(formula, Or):
        return f"({format_formula(formula.left)} | {format_formula(formula.right)})"
    if isinstance(formula, Eventually):
        return f"F({format_formula(formula.operand)})"
    if isinstance(formula, Always):
        return f"G({format_formula(formula.operand)})"
    if isinstance(formula, Implies):
        return f"({format_formula(formula.antecedent)} -> {format_formula(formula.consequent)})"
    if isinstance(formula, BoundedEventually):
        return f"F[{formula.lower},{formula.upper}]({format_formula(formula.operand)})"
    if isinstance(formula, Until):
        return f"({format_formula(formula.left)} U {format_formula(formula.right)})"
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")
