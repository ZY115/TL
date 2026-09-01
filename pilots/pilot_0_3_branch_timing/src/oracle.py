"""Independent oracle for conditional branch/timing semantics."""

from __future__ import annotations

from collections.abc import Sequence

from .model import Stage


def branch_timing_oracle(trajectory: Sequence[str], stages: Sequence[Stage]) -> bool:
    """Evaluate the Pilot 0.3 mathematical task definition directly."""

    if not trajectory or trajectory[0] != "S":
        return False
    named_events = [event for event in trajectory if event != "O"]
    if len(named_events) != len(set(named_events)):
        return False
    if "E" not in named_events:
        return False

    positions = {event: step for step, event in enumerate(trajectory) if event != "O"}
    end_position = positions["E"]
    previous_choice_position = -1
    selected: list[tuple[Stage, str, int, str, int]] = []

    for stage in stages:
        left_present = stage.left_event in positions
        right_present = stage.right_event in positions
        if left_present == right_present:
            return False
        if left_present:
            choice = stage.left_event
            goal = stage.left_goal
            bound = stage.left_bound
        else:
            choice = stage.right_event
            goal = stage.right_goal
            bound = stage.right_bound
        choice_position = positions[choice]
        if choice_position <= previous_choice_position:
            return False
        previous_choice_position = choice_position
        selected.append((stage, choice, choice_position, goal, bound))

    for _stage, _choice, choice_position, goal, bound in selected:
        if goal not in positions:
            return False
        goal_position = positions[goal]
        difference = goal_position - choice_position
        if not 1 <= difference <= bound:
            return False
        if goal_position >= end_position:
            return False

    if stages and end_position <= previous_choice_position:
        return False
    return True
