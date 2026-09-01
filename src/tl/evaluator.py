"""Finite-trace evaluator for Atom, And, and Eventually."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from .syntax import And, Atom, Eventually, Formula


def evaluate(formula: Formula, trajectory: Sequence[str]) -> bool:
    """Evaluate a formula at position zero under finite-trace semantics."""

    trace = tuple(trajectory)

    @lru_cache(maxsize=None)
    def evaluate_at(node: Formula, position: int) -> bool:
        if isinstance(node, Atom):
            return position < len(trace) and trace[position] == node.name
        if isinstance(node, And):
            return evaluate_at(node.left, position) and evaluate_at(
                node.right, position
            )
        if isinstance(node, Eventually):
            return any(
                evaluate_at(node.operand, future)
                for future in range(position, len(trace))
            )
        raise TypeError(f"Unsupported formula node: {type(node)!r}")

    return evaluate_at(formula, 0)
