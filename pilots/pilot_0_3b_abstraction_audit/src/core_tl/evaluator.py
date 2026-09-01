"""Finite-trace semantics for the Pilot 0.3 bounded-TL fragment."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

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


def evaluate(formula: Formula, trajectory: Sequence[str]) -> bool:
    trace = tuple(trajectory)

    @lru_cache(maxsize=None)
    def evaluate_at(node: Formula, position: int) -> bool:
        if isinstance(node, Atom):
            return position < len(trace) and trace[position] == node.name
        if isinstance(node, Not):
            return not evaluate_at(node.operand, position)
        if isinstance(node, And):
            return evaluate_at(node.left, position) and evaluate_at(
                node.right, position
            )
        if isinstance(node, Or):
            return evaluate_at(node.left, position) or evaluate_at(node.right, position)
        if isinstance(node, Eventually):
            return any(
                evaluate_at(node.operand, future)
                for future in range(position, len(trace))
            )
        if isinstance(node, Always):
            return all(
                evaluate_at(node.operand, future)
                for future in range(position, len(trace))
            )
        if isinstance(node, Implies):
            return (not evaluate_at(node.antecedent, position)) or evaluate_at(
                node.consequent, position
            )
        if isinstance(node, BoundedEventually):
            start = position + node.lower
            stop = min(position + node.upper, len(trace) - 1)
            if start > stop:
                return False
            return any(
                evaluate_at(node.operand, future) for future in range(start, stop + 1)
            )
        raise TypeError(f"Unsupported formula node: {type(node)!r}")

    return bool(trace) and evaluate_at(formula, 0)
