"""Syntax and deterministic pretty-printing for the benchmark TL fragment."""

from __future__ import annotations

from dataclasses import dataclass


class Formula:
    """Marker base class for benchmark formulas."""


@dataclass(frozen=True, slots=True)
class Atom(Formula):
    name: str


@dataclass(frozen=True, slots=True)
class And(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True, slots=True)
class Eventually(Formula):
    operand: Formula


def pretty(formula: Formula) -> str:
    """Return the unique canonical source form used for measurement."""

    if isinstance(formula, Atom):
        return formula.name
    if isinstance(formula, And):
        return f"{pretty(formula.left)} & {pretty(formula.right)}"
    if isinstance(formula, Eventually):
        return f"F({pretty(formula.operand)})"
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def structural_counts(formula: Formula) -> dict[str, int]:
    """Count TL nodes, operators, atoms, and node-level maximum depth."""

    def walk(node: Formula, depth: int) -> tuple[int, int, int, int, int]:
        if isinstance(node, Atom):
            return 1, 1, 0, 0, depth
        if isinstance(node, Eventually):
            nodes, atoms, eventually, conjunctions, max_depth = walk(
                node.operand, depth + 1
            )
            return nodes + 1, atoms, eventually + 1, conjunctions, max_depth
        if isinstance(node, And):
            left = walk(node.left, depth + 1)
            right = walk(node.right, depth + 1)
            return (
                left[0] + right[0] + 1,
                left[1] + right[1],
                left[2] + right[2],
                left[3] + right[3] + 1,
                max(left[4], right[4]),
            )
        raise TypeError(f"Unsupported formula node: {type(node)!r}")

    nodes, atoms, eventually, conjunctions, depth = walk(formula, 1)
    return {
        "tl_ast_nodes": nodes,
        "tl_atoms": atoms,
        "tl_eventually": eventually,
        "tl_and": conjunctions,
        "tl_ast_depth": depth,
    }
