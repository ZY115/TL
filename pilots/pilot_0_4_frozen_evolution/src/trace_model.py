"""Shared one-event-per-step trace model for Pilot 0.4."""

from __future__ import annotations

from collections.abc import Sequence, Set

from .model import Stage

EXTRA_EVENTS = (
    "BAD",
    "Z2",
    "H",
    "REC",
    "Y3",
    "N1",
    "N2",
    "J",
    "C",
    "D",
)


def task_alphabet(stages: Sequence[Stage]) -> frozenset[str]:
    events = {"O", "S", "E", *EXTRA_EVENTS}
    for stage in stages:
        events.update(
            {
                stage.left_event,
                stage.left_goal,
                stage.right_event,
                stage.right_goal,
            }
        )
    return frozenset(events)


def validate_trace_model(trajectory: Sequence[str], alphabet: Set[str]) -> bool:
    """Check the environment assumptions, not task satisfaction."""

    seen_named: set[str] = set()
    for event in trajectory:
        if not isinstance(event, str) or event not in alphabet:
            return False
        if event != "O":
            if event in seen_named:
                return False
            seen_named.add(event)
    return True
