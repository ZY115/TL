"""E3 interpreter with bounded responses."""

from __future__ import annotations

from collections.abc import Sequence


def evaluate(config: dict[str, object], trajectory: Sequence[str]) -> bool:
    if not trajectory or trajectory[0] != "S" or "E" not in trajectory:
        return False
    positions = {event: index for index, event in enumerate(trajectory) if event != "O"}
    end = positions["E"]
    previous_choice = -1
    selected: list[tuple[int, str, int]] = []
    stages = config["STAGES"]
    assert isinstance(stages, list)
    for row in stages:
        left_event, left_goal, left_bound, right_event, right_goal, right_bound = row
        left_present = left_event in positions
        right_present = right_event in positions
        if left_present == right_present:
            return False
        if left_present:
            choice_position = positions[left_event]
            goal = left_goal
            bound = left_bound
        else:
            choice_position = positions[right_event]
            goal = right_goal
            bound = right_bound
        if choice_position <= previous_choice:
            return False
        previous_choice = choice_position
        selected.append((choice_position, goal, bound))
    for choice_position, goal, bound in selected:
        if goal not in positions:
            return False
        goal_position = positions[goal]
        if not 1 <= goal_position - choice_position <= bound or goal_position >= end:
            return False
    global_avoid = config["GLOBAL_AVOID"]
    assert isinstance(global_avoid, list)
    if any(event in positions and positions[event] < end for event in global_avoid):
        return False
    branch_sequences = config["BRANCH_POST_SEQUENCES"]
    assert isinstance(branch_sequences, list)
    for trigger, sequence in branch_sequences:
        if trigger in positions:
            cursor = positions[trigger]
            for event in sequence:
                if event not in positions or positions[event] <= cursor:
                    return False
                cursor = positions[event]
            if cursor >= end:
                return False
    bounded_responses = config["BOUNDED_RESPONSES"]
    assert isinstance(bounded_responses, list)
    for trigger, response, bound in bounded_responses:
        if trigger in positions:
            if response not in positions:
                return False
            difference = positions[response] - positions[trigger]
            if not 1 <= difference <= bound or positions[response] >= end:
                return False
    return end > previous_choice
