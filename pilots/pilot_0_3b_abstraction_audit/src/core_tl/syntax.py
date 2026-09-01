"""Syntax, canonical printing, and structural counts for Pilot 0.3 TL."""

from __future__ import annotations

from dataclasses import dataclass


class Formula:
    """Marker base class for the benchmark fragment."""


@dataclass(frozen=True, slots=True)
class Atom(Formula):
    name: str


@dataclass(frozen=True, slots=True)
class Not(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class And(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True, slots=True)
class Or(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True, slots=True)
class Eventually(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class Always(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class Implies(Formula):
    antecedent: Formula
    consequent: Formula


@dataclass(frozen=True, slots=True)
class BoundedEventually(Formula):
    lower: int
    upper: int
    operand: Formula


def pretty(formula: Formula) -> str:
    if isinstance(formula, Atom):
        return formula.name
    if isinstance(formula, Not):
        return f"!({pretty(formula.operand)})"
    if isinstance(formula, And):
        return f"({pretty(formula.left)} & {pretty(formula.right)})"
    if isinstance(formula, Or):
        return f"({pretty(formula.left)} | {pretty(formula.right)})"
    if isinstance(formula, Eventually):
        return f"F({pretty(formula.operand)})"
    if isinstance(formula, Always):
        return f"G({pretty(formula.operand)})"
    if isinstance(formula, Implies):
        return f"({pretty(formula.antecedent)} -> {pretty(formula.consequent)})"
    if isinstance(formula, BoundedEventually):
        return f"F[{formula.lower},{formula.upper}]({pretty(formula.operand)})"
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def _top_level_conjuncts(formula: Formula) -> list[Formula]:
    if isinstance(formula, And):
        return [*_top_level_conjuncts(formula.left), formula.right]
    return [formula]


def pretty_task(formula: Formula) -> str:
    """Print one deterministic top-level conjunct per line."""

    return " &\n".join(pretty(item) for item in _top_level_conjuncts(formula)) + "\n"


def structural_counts(formula: Formula) -> dict[str, int]:
    counters = {
        "tl_ast_nodes": 0,
        "tl_atoms": 0,
        "tl_not": 0,
        "tl_and": 0,
        "tl_or": 0,
        "tl_eventually": 0,
        "tl_always": 0,
        "tl_implication": 0,
        "tl_bounded_eventually": 0,
        "tl_ast_depth": 0,
    }

    def walk(node: Formula, depth: int) -> None:
        counters["tl_ast_nodes"] += 1
        counters["tl_ast_depth"] = max(counters["tl_ast_depth"], depth)
        if isinstance(node, Atom):
            counters["tl_atoms"] += 1
        elif isinstance(node, Not):
            counters["tl_not"] += 1
            walk(node.operand, depth + 1)
        elif isinstance(node, And):
            counters["tl_and"] += 1
            walk(node.left, depth + 1)
            walk(node.right, depth + 1)
        elif isinstance(node, Or):
            counters["tl_or"] += 1
            walk(node.left, depth + 1)
            walk(node.right, depth + 1)
        elif isinstance(node, Eventually):
            counters["tl_eventually"] += 1
            walk(node.operand, depth + 1)
        elif isinstance(node, Always):
            counters["tl_always"] += 1
            walk(node.operand, depth + 1)
        elif isinstance(node, Implies):
            counters["tl_implication"] += 1
            walk(node.antecedent, depth + 1)
            walk(node.consequent, depth + 1)
        elif isinstance(node, BoundedEventually):
            counters["tl_bounded_eventually"] += 1
            walk(node.operand, depth + 1)
        else:  # pragma: no cover
            raise TypeError(f"Unsupported formula node: {type(node)!r}")

    walk(formula, 1)
    return counters
