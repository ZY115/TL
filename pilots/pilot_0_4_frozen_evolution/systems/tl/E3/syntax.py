"""Frozen E0 Core-TL syntax. Until is intentionally absent."""

from __future__ import annotations

from dataclasses import dataclass


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
