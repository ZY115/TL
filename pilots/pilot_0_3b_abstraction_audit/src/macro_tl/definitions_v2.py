"""Macro definition V2: compose equivalent reusable helper macros."""

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


def exclusive_choice(left: str, right: str) -> tuple[Formula, Formula]:
    return (
        Always(Implies(Atom(left), Always(Not(Atom(right))))),
        Always(Implies(Atom(right), Always(Not(Atom(left))))),
    )


def bounded_response(trigger: str, goal: str, bound: int, end: str) -> Formula:
    return Always(
        Implies(
            Atom(trigger),
            BoundedEventually(
                1,
                bound,
                And(Atom(goal), Eventually(Atom(end))),
            ),
        )
    )


def timed_choice_stage(stage: Stage, end: str) -> tuple[Formula, ...]:
    return (
        *exclusive_choice(stage.left_event, stage.right_event),
        bounded_response(stage.left_event, stage.left_goal, stage.left_bound, end),
        bounded_response(
            stage.right_event,
            stage.right_goal,
            stage.right_bound,
            end,
        ),
    )
