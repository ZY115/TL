"""Generate canonical TL formulas for ordered sequences."""

from __future__ import annotations

from collections.abc import Sequence

from src.tree_diff import TreeNode

from .syntax import And, Atom, Eventually, Formula


def sequence_formula(targets: Sequence[str]) -> Formula:
    """Build ``F(A1 & F(A2 & ... F(An)))`` for non-empty targets."""

    if not targets:
        raise ValueError("Pilot 0.1 tasks require at least one target")

    result: Formula = Eventually(Atom(targets[-1]))
    for target in reversed(targets[:-1]):
        result = Eventually(And(Atom(target), result))
    return result


def formula_tree(formula: Formula) -> TreeNode:
    """Convert a TL AST to its normalized ordered tree."""

    if isinstance(formula, Atom):
        return TreeNode(f"Atom:{formula.name}")
    if isinstance(formula, Eventually):
        return TreeNode("Eventually", (formula_tree(formula.operand),))
    if isinstance(formula, And):
        return TreeNode(
            "And", (formula_tree(formula.left), formula_tree(formula.right))
        )
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")
