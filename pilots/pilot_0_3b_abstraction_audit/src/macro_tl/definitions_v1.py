"""Macro definition V1: direct expansion into four Core-TL clauses."""

from __future__ import annotations

from ..core_tl.syntax import (
    Always,
    And,
    Atom,
    BoundedEventually,
    Eventually,
    Formula,
    Implies,
    Not,
)
from ..model import Stage


def timed_choice_stage(stage: Stage, end: str) -> tuple[Formula, ...]:
    return (
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
    )
