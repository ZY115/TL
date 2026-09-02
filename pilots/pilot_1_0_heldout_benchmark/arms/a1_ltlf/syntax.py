"""Frozen A1 syntax learned from individual training primitives."""

from __future__ import annotations

from dataclasses import dataclass


class Formula:
    pass


@dataclass(frozen=True, slots=True)
class Atom(Formula):
    name: str


@dataclass(frozen=True, slots=True)
class ResourceComparison(Formula):
    resource: str
    operator: str
    value: int


@dataclass(frozen=True, slots=True)
class Not(Formula):
    operand: Formula


@dataclass(frozen=True, slots=True)
class And(Formula):
    operands: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class Or(Formula):
    operands: tuple[Formula, ...]


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


@dataclass(frozen=True, slots=True)
class Implies(Formula):
    antecedent: Formula
    consequent: Formula


@dataclass(frozen=True, slots=True)
class CountAtMostFormula(Formula):
    atom: Atom
    maximum: int


@dataclass(frozen=True, slots=True)
class OnceFormula(Formula):
    atom: Atom


@dataclass(frozen=True, slots=True)
class SinceFormula(Formula):
    condition: Atom
    landmark: Atom


@dataclass(frozen=True, slots=True)
class PriorityFormula(Formula):
    options: tuple[Formula, ...]
