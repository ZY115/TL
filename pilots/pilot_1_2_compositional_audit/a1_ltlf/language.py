"""A fixed standard future-time LTLf fragment with strong next."""

from __future__ import annotations

import re
from dataclasses import dataclass


class FormulaSyntaxError(ValueError):
    """Raised when candidate text is outside the frozen A1 grammar."""


class Formula:
    pass


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
class Implies(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True, slots=True)
class Next(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class Eventually(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class Always(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class Until(Formula):
    left: Formula
    right: Formula


_TOKEN = re.compile(r"\s*(->|[()!&|]|[A-Za-z_][A-Za-z0-9_]*)")
_UNARY = {"!", "X", "F", "G"}


def _tokens(source: str) -> tuple[str, ...]:
    source = source.strip()
    result: list[str] = []
    offset = 0
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if match is None:
            raise FormulaSyntaxError(f"unexpected character at offset {offset}")
        result.append(match.group(1))
        offset = match.end()
    if not result:
        raise FormulaSyntaxError("empty formula")
    return tuple(result)


class _Parser:
    def __init__(self, source: str):
        self.values = _tokens(source)
        self.index = 0

    @property
    def current(self) -> str | None:
        return self.values[self.index] if self.index < len(self.values) else None

    def accept(self, value: str) -> bool:
        if self.current == value:
            self.index += 1
            return True
        return False

    def parse(self) -> Formula:
        result = self.implication()
        if self.current is not None:
            raise FormulaSyntaxError(f"unexpected token {self.current!r}")
        return result

    def implication(self) -> Formula:
        left = self.disjunction()
        if self.accept("->"):
            return Implies(left, self.implication())
        return left

    def disjunction(self) -> Formula:
        result = self.conjunction()
        while self.accept("|"):
            result = Or(result, self.conjunction())
        return result

    def conjunction(self) -> Formula:
        result = self.until()
        while self.accept("&"):
            result = And(result, self.until())
        return result

    def until(self) -> Formula:
        left = self.unary()
        if self.accept("U"):
            return Until(left, self.until())
        return left

    def unary(self) -> Formula:
        token = self.current
        if token in _UNARY:
            self.index += 1
            operand = self.unary()
            return {
                "!": Not,
                "X": Next,
                "F": Eventually,
                "G": Always,
            }[
                token
            ](operand)
        if self.accept("("):
            result = self.implication()
            if not self.accept(")"):
                raise FormulaSyntaxError("missing closing parenthesis")
            return result
        if token is None or token in {"U", ")", "->", "&", "|"}:
            raise FormulaSyntaxError(f"expected formula, found {token!r}")
        self.index += 1
        if token in _UNARY:
            raise FormulaSyntaxError(f"operator {token!r} cannot be an atom")
        return Atom(token)


def parse_formula(source: str) -> Formula:
    return _Parser(source).parse()


def _atom_true(name: str, propositions: frozenset[str]) -> bool:
    label = name[3:] if name.startswith("at_") else name
    return label in propositions


def evaluate(
    formula: Formula,
    trace: tuple[frozenset[str], ...],
    position: int = 0,
) -> bool:
    if isinstance(formula, Atom):
        return position < len(trace) and _atom_true(formula.name, trace[position])
    if isinstance(formula, Not):
        return not evaluate(formula.operand, trace, position)
    if isinstance(formula, And):
        return evaluate(formula.left, trace, position) and evaluate(
            formula.right, trace, position
        )
    if isinstance(formula, Or):
        return evaluate(formula.left, trace, position) or evaluate(
            formula.right, trace, position
        )
    if isinstance(formula, Implies):
        return not evaluate(formula.left, trace, position) or evaluate(
            formula.right, trace, position
        )
    if isinstance(formula, Next):
        return position + 1 < len(trace) and evaluate(
            formula.operand, trace, position + 1
        )
    if isinstance(formula, Eventually):
        return any(
            evaluate(formula.operand, trace, index)
            for index in range(position, len(trace))
        )
    if isinstance(formula, Always):
        return all(
            evaluate(formula.operand, trace, index)
            for index in range(position, len(trace))
        )
    if isinstance(formula, Until):
        return any(
            evaluate(formula.right, trace, endpoint)
            and all(
                evaluate(formula.left, trace, index)
                for index in range(position, endpoint)
            )
            for endpoint in range(position, len(trace))
        )
    raise TypeError(type(formula))


def format_formula(formula: Formula) -> str:
    if isinstance(formula, Atom):
        return formula.name
    if isinstance(formula, Not):
        return f"!({format_formula(formula.operand)})"
    if isinstance(formula, And):
        return f"({format_formula(formula.left)} & {format_formula(formula.right)})"
    if isinstance(formula, Or):
        return f"({format_formula(formula.left)} | {format_formula(formula.right)})"
    if isinstance(formula, Implies):
        return f"({format_formula(formula.left)} -> {format_formula(formula.right)})"
    if isinstance(formula, Next):
        return f"X({format_formula(formula.operand)})"
    if isinstance(formula, Eventually):
        return f"F({format_formula(formula.operand)})"
    if isinstance(formula, Always):
        return f"G({format_formula(formula.operand)})"
    if isinstance(formula, Until):
        return f"({format_formula(formula.left)} U {format_formula(formula.right)})"
    raise TypeError(type(formula))
