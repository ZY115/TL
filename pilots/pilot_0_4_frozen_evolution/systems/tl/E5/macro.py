"""Frozen START/END/ORDERED_CHOICES/TIMED_CHOICE_STAGE expansion."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

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


@dataclass(frozen=True, slots=True)
class Stage:
    index: int
    left_event: str
    left_goal: str
    left_bound: int
    right_event: str
    right_goal: str
    right_bound: int


def build_base_formula(start: str, end: str, stages: tuple[Stage, ...]) -> Formula:
    tail: Formula = Eventually(Atom(end))
    for stage in reversed(stages):
        choice = Or(Atom(stage.left_event), Atom(stage.right_event))
        tail = Eventually(And(choice, tail))
    clauses: list[Formula] = [And(Atom(start), tail)]
    for stage in stages:
        clauses.extend(
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
                            And(Atom(stage.left_goal), Eventually(Atom(end))),
                        ),
                    )
                ),
                Always(
                    Implies(
                        Atom(stage.right_event),
                        BoundedEventually(
                            1,
                            stage.right_bound,
                            And(Atom(stage.right_goal), Eventually(Atom(end))),
                        ),
                    )
                ),
            ]
        )
    return reduce(And, clauses)
