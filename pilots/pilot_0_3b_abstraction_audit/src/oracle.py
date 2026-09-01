"""Independent oracle, assuming the shared trace model has been validated."""

from __future__ import annotations

from collections.abc import Sequence

from .model import Stage


def branch_timing_oracle(trajectory: Sequence[str], stages: Sequence[Stage]) -> bool:
    if not trajectory or trajectory[0] != "S" or "E" not in trajectory:
        return False

    positions = {event: step for step, event in enumerate(trajectory) if event != "O"}
    end_position = positions["E"]
    previous_choice_position = -1
    selected: list[tuple[int, str, int]] = []

    for stage in stages:
        left_present = stage.left_event in positions
        right_present = stage.right_event in positions
        if left_present == right_present:
            return False
        if left_present:
            choice_position = positions[stage.left_event]
            goal = stage.left_goal
            bound = stage.left_bound
        else:
            choice_position = positions[stage.right_event]
            goal = stage.right_goal
            bound = stage.right_bound
        if choice_position <= previous_choice_position:
            return False
        previous_choice_position = choice_position
        selected.append((choice_position, goal, bound))

    for choice_position, goal, bound in selected:
        if goal not in positions:
            return False
        goal_position = positions[goal]
        if not 1 <= goal_position - choice_position <= bound:
            return False
        if goal_position >= end_position:
            return False

    return not stages or end_position > previous_choice_position
