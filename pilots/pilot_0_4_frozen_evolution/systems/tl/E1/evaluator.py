"""Finite-trace E0 evaluator. Until is intentionally absent."""

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
    def at(node: Formula, position: int) -> bool:
        if isinstance(node, Atom):
            return position < len(trace) and trace[position] == node.name
        if isinstance(node, Not):
            return not at(node.operand, position)
        if isinstance(node, And):
            return at(node.left, position) and at(node.right, position)
        if isinstance(node, Or):
            return at(node.left, position) or at(node.right, position)
        if isinstance(node, Eventually):
            return any(
                at(node.operand, future) for future in range(position, len(trace))
            )
        if isinstance(node, Always):
            return all(
                at(node.operand, future) for future in range(position, len(trace))
            )
        if isinstance(node, Implies):
            return (not at(node.antecedent, position)) or at(node.consequent, position)
        if isinstance(node, BoundedEventually):
            start = position + node.lower
            stop = min(position + node.upper, len(trace) - 1)
            return start <= stop and any(
                at(node.operand, future) for future in range(start, stop + 1)
            )
        raise TypeError(f"Unsupported formula node: {type(node)!r}")

    return bool(trace) and at(formula, 0)
