"""Independent mathematical oracle for cumulative requirement evolution."""

from __future__ import annotations

from collections.abc import Sequence

from .model import Stage, stages_for_k

REQUIREMENT_KEYS = (
    "global_avoid",
    "branch_post_sequence_E2",
    "bounded_recovery",
    "avoid_until",
    "branch_post_sequence_E5",
    "alternative_recovery",
)


def branch_timing_oracle(trajectory: Sequence[str], stages: Sequence[Stage]) -> bool:
    """Direct B_k oracle copied semantically from the frozen source pilot."""

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


def _ordered_before(
    positions: dict[str, int], trigger: str, events: Sequence[str], end: int
) -> bool:
    if trigger not in positions:
        return True
    cursor = positions[trigger]
    for event in events:
        if event not in positions or positions[event] <= cursor:
            return False
        cursor = positions[event]
    return cursor < end


def evolution_oracle_diagnostics(
    trajectory: Sequence[str], evolution_step: int
) -> dict[str, bool | None]:
    """Return one independent diagnostic for every cumulative requirement."""

    if not 0 <= evolution_step <= 6:
        raise ValueError("evolution_step must be in 0..6")
    base = branch_timing_oracle(trajectory, stages_for_k(4))
    positions = {event: step for step, event in enumerate(trajectory) if event != "O"}
    end = positions.get("E", -1)
    diagnostics: dict[str, bool | None] = {
        "base_B4": base,
        **{key: None for key in REQUIREMENT_KEYS},
    }
    if evolution_step >= 1:
        # The canonical task ends at E. This is equivalent to G(!BAD) on all
        # generated legal traces and matches GLOBAL_AVOID's declared scope.
        diagnostics["global_avoid"] = "BAD" not in positions or positions["BAD"] > end
    if evolution_step >= 2:
        diagnostics["branch_post_sequence_E2"] = _ordered_before(
            positions, "L2", ("P2", "Z2"), end
        )
    if evolution_step >= 3:
        if "H" not in positions:
            diagnostics["bounded_recovery"] = True
        else:
            diagnostics["bounded_recovery"] = (
                "REC" in positions
                and 1 <= positions["REC"] - positions["H"] <= 3
                and positions["REC"] < end
            )
    if evolution_step >= 4:
        if "R3" not in positions:
            diagnostics["avoid_until"] = True
        else:
            diagnostics["avoid_until"] = (
                "Q3" in positions
                and positions["Q3"] > positions["R3"]
                and not (
                    "Y3" in positions
                    and positions["R3"] < positions["Y3"] < positions["Q3"]
                )
            )
    if evolution_step >= 5:
        diagnostics["branch_post_sequence_E5"] = _ordered_before(
            positions, "L4", ("P4", "N1", "N2"), end
        )
    if evolution_step >= 6:
        if "J" not in positions:
            diagnostics["alternative_recovery"] = True
        else:
            diagnostics["alternative_recovery"] = any(
                response in positions
                and 1 <= positions[response] - positions["J"] <= bound
                and positions[response] < end
                for response, bound in (("C", 2), ("D", 5))
            )
    return diagnostics


def evolution_oracle(trajectory: Sequence[str], evolution_step: int) -> bool:
    diagnostics = evolution_oracle_diagnostics(trajectory, evolution_step)
    return all(value is not False for value in diagnostics.values())
