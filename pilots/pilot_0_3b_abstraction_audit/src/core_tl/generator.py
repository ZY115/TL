"""Canonical branch/timing formula generator and normalized tree."""

from __future__ import annotations

from collections.abc import Sequence
from functools import reduce

from ..model import Stage
from ..tree_diff import TreeNode
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
)


def _and_all(conjuncts: Sequence[Formula]) -> Formula:
    if not conjuncts:
        raise ValueError("At least one conjunct is required")
    return reduce(And, conjuncts)


def _decision_sequence(stages: Sequence[Stage]) -> Formula:
    tail: Formula = Eventually(Atom("E"))
    for stage in reversed(stages):
        choice = Or(Atom(stage.left_event), Atom(stage.right_event))
        tail = Eventually(And(choice, tail))
    return And(Atom("S"), tail)


def task_formula(stages: Sequence[Stage]) -> Formula:
    conjuncts: list[Formula] = [_decision_sequence(stages)]
    for stage in stages:
        conjuncts.extend(
            [
                Always(
                    Implies(
                        Atom(stage.left_event),
                        Always(Not(Atom(stage.right_event))),
                    )
                ),
                Always(
                    Implies(
                        Atom(stage.right_event),
                        Always(Not(Atom(stage.left_event))),
                    )
                ),
                Always(
                    Implies(
                        Atom(stage.left_event),
                        BoundedEventually(
                            1,
                            stage.left_bound,
                            And(Atom(stage.left_goal), Eventually(Atom("E"))),
                        ),
                    )
                ),
                Always(
                    Implies(
                        Atom(stage.right_event),
                        BoundedEventually(
                            1,
                            stage.right_bound,
                            And(Atom(stage.right_goal), Eventually(Atom("E"))),
                        ),
                    )
                ),
            ]
        )
    return _and_all(conjuncts)


def formula_tree(formula: Formula) -> TreeNode:
    if isinstance(formula, Atom):
        return TreeNode(f"Atom:{formula.name}")
    if isinstance(formula, Not):
        return TreeNode("Not", (formula_tree(formula.operand),))
    if isinstance(formula, And):
        return TreeNode(
            "And", (formula_tree(formula.left), formula_tree(formula.right))
        )
    if isinstance(formula, Or):
        return TreeNode("Or", (formula_tree(formula.left), formula_tree(formula.right)))
    if isinstance(formula, Eventually):
        return TreeNode("Eventually", (formula_tree(formula.operand),))
    if isinstance(formula, Always):
        return TreeNode("Always", (formula_tree(formula.operand),))
    if isinstance(formula, Implies):
        return TreeNode(
            "Implies",
            (formula_tree(formula.antecedent), formula_tree(formula.consequent)),
        )
    if isinstance(formula, BoundedEventually):
        return TreeNode(
            f"BoundedEventually[{formula.lower},{formula.upper}]",
            (formula_tree(formula.operand),),
        )
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")
