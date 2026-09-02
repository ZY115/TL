"""Normalized formula trees with strong Until support."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class Node:
    label: str
    children: tuple["Node", ...] = ()


def formula_tree(formula: Formula) -> Node:
    if isinstance(formula, Atom):
        return Node(f"Atom:{formula.name}")
    if isinstance(formula, Not):
        return Node("Not", (formula_tree(formula.operand),))
    if isinstance(formula, And):
        return Node("And", (formula_tree(formula.left), formula_tree(formula.right)))
    if isinstance(formula, Or):
        return Node("Or", (formula_tree(formula.left), formula_tree(formula.right)))
    if isinstance(formula, Eventually):
        return Node("Eventually", (formula_tree(formula.operand),))
    if isinstance(formula, Always):
        return Node("Always", (formula_tree(formula.operand),))
    if isinstance(formula, Implies):
        return Node(
            "Implies",
            (formula_tree(formula.antecedent), formula_tree(formula.consequent)),
        )
    if isinstance(formula, BoundedEventually):
        return Node(
            f"BoundedEventually[{formula.lower},{formula.upper}]",
            (formula_tree(formula.operand),),
        )
    if isinstance(formula, Until):
        return Node("Until", (formula_tree(formula.left), formula_tree(formula.right)))
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")
