"""Shared environment-level trace validation for Pilot 0.3B."""

from __future__ import annotations

from collections.abc import Sequence, Set

from .model import Stage


def task_alphabet(
    stages: Sequence[Stage], *, additional_events: Sequence[str] = ()
) -> frozenset[str]:
    events = {"O", "S", "E", *additional_events}
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
    """Check only environment assumptions, not task satisfaction."""

    seen_named: set[str] = set()
    for event in trajectory:
        if not isinstance(event, str) or event not in alphabet:
            return False
        if event != "O":
            if event in seen_named:
                return False
            seen_named.add(event)
    return True
