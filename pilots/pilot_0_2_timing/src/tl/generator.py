"""Generate sequence-plus-deadline bounded-TL tasks."""

from __future__ import annotations

from collections.abc import Sequence

from src.model import TimingConstraint
from src.tree_diff import TreeNode

from .syntax import (
    Always,
    And,
    Atom,
    BoundedEventually,
    Eventually,
    Formula,
    Implies,
)


def sequence_formula(targets: Sequence[str]) -> Formula:
    if not targets:
        raise ValueError("Pilot 0.2 requires a non-empty sequence")
    result: Formula = Eventually(Atom(targets[-1]))
    for target in reversed(targets[:-1]):
        result = Eventually(And(Atom(target), result))
    return result


def timing_formula(constraint: TimingConstraint) -> Formula:
    return Always(
        Implies(
            Atom(constraint.start),
            BoundedEventually(constraint.lower, constraint.bound, Atom(constraint.end)),
        )
    )


def task_formula(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> Formula:
    result = sequence_formula(targets)
    for constraint in timing_constraints:
        result = And(result, timing_formula(constraint))
    return result


def formula_tree(formula: Formula) -> TreeNode:
    if isinstance(formula, Atom):
        return TreeNode(f"Atom:{formula.name}")
    if isinstance(formula, And):
        return TreeNode(
            "And", (formula_tree(formula.left), formula_tree(formula.right))
        )
    if isinstance(formula, Eventually):
        return TreeNode("Eventually", (formula_tree(formula.operand),))
    if isinstance(formula, Always):
        return TreeNode("Always", (formula_tree(formula.operand),))
    if isinstance(formula, Implies):
        return TreeNode(
            "Implies",
            (
                formula_tree(formula.antecedent),
                formula_tree(formula.consequent),
            ),
        )
    if isinstance(formula, BoundedEventually):
        return TreeNode(
            f"BoundedEventually[{formula.lower},{formula.upper}]",
            (formula_tree(formula.operand),),
        )
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")
