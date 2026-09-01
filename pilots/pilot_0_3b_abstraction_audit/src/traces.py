"""Deterministic and structured-random trace generation for Pilot 0.3."""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence

from .model import Stage


def _choice_goal(stage: Stage, branch: str) -> tuple[str, str, int]:
    if branch == "L":
        return stage.left_event, stage.left_goal, stage.left_bound
    if branch == "R":
        return stage.right_event, stage.right_goal, stage.right_bound
    raise ValueError(f"Unknown branch: {branch}")


def canonical_trace(stages: Sequence[Stage], branches: Sequence[str]) -> list[str]:
    selected = [_choice_goal(stage, branch) for stage, branch in zip(stages, branches)]
    return [
        "S",
        *(choice for choice, _goal, _bound in selected),
        *(goal for _choice, goal, _bound in selected),
        "E",
    ]


def branch_assignment_traces(stages: Sequence[Stage]) -> list[list[str]]:
    if not stages:
        return [["S", "E"]]
    return [
        canonical_trace(stages, branches)
        for branches in itertools.product("LR", repeat=len(stages))
    ]


def deadline_boundary_traces(
    stages: Sequence[Stage], *, difference_offset: int
) -> list[list[str]]:
    """Cover both branch bounds at offset 0 (inclusive) or 1 (failure)."""

    traces = []
    for target_index, target in enumerate(stages):
        for target_branch in "LR":
            trace = ["S"]
            for stage in stages[:target_index]:
                choice, goal, _bound = _choice_goal(stage, "L")
                trace.extend([choice, goal])
            choice, goal, bound = _choice_goal(target, target_branch)
            trace.append(choice)
            difference = bound + difference_offset
            trace.extend(["O"] * (difference - 1))
            trace.append(goal)
            for stage in stages[target_index + 1 :]:
                later_choice, later_goal, _later_bound = _choice_goal(stage, "L")
                trace.extend([later_choice, later_goal])
            trace.append("E")
            traces.append(trace)
    return traces


def missing_decision_traces(stages: Sequence[Stage]) -> list[list[str]]:
    base = canonical_trace(stages, ["L"] * len(stages))
    return [
        [event for event in base if event not in {stage.left_event, stage.left_goal}]
        for stage in stages
    ]


def both_branches_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for stage in stages:
        trace = canonical_trace(stages, ["L"] * len(stages))
        position = trace.index(stage.left_event)
        trace.insert(position + 1, stage.right_event)
        traces.append(trace)
    return traces


def decision_order_violation_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for index in range(len(stages) - 1):
        trace = canonical_trace(stages, ["L"] * len(stages))
        first = trace.index(stages[index].left_event)
        second = trace.index(stages[index + 1].left_event)
        trace[first], trace[second] = trace[second], trace[first]
        traces.append(trace)
    return traces


def missing_selected_goal_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for index, stage in enumerate(stages):
        branches = ["L"] * len(stages)
        trace = canonical_trace(stages, branches)
        trace.remove(stage.left_goal)
        traces.append(trace)
    return traces


def wrong_goal_only_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for target_index, stage in enumerate(stages):
        for branch in "LR":
            branches = ["L"] * len(stages)
            branches[target_index] = branch
            trace = canonical_trace(stages, branches)
            _choice, selected_goal, _bound = _choice_goal(stage, branch)
            wrong_goal = stage.right_goal if branch == "L" else stage.left_goal
            trace[trace.index(selected_goal)] = wrong_goal
            traces.append(trace)
    return traces


def goal_before_choice_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for target_index, stage in enumerate(stages):
        for branch in "LR":
            branches = ["L"] * len(stages)
            branches[target_index] = branch
            trace = canonical_trace(stages, branches)
            choice, goal, _bound = _choice_goal(stage, branch)
            trace.remove(goal)
            trace.insert(trace.index(choice), goal)
            traces.append(trace)
    return traces


def end_too_early_traces(stages: Sequence[Stage]) -> list[list[str]]:
    traces = []
    for stage in stages:
        trace = canonical_trace(stages, ["L"] * len(stages))
        trace.remove("E")
        trace.insert(trace.index(stage.left_goal), "E")
        traces.append(trace)
    return traces


def goal_reordering_traces(stages: Sequence[Stage]) -> list[list[str]]:
    if not stages:
        return []
    choices_goals = [_choice_goal(stage, "R") for stage in stages]
    choices = [item[0] for item in choices_goals]
    goals = [item[1] for item in choices_goals]
    if len(stages) <= 5:
        order = list(reversed(range(len(stages))))
    else:
        # A full reversal makes stage 1's distance 11, beyond its right bound 10.
        order = [5, 4, 3, 0, 1, 2]
    return [["S", *choices, *(goals[index] for index in order), "E"]]


def infeasible_full_reverse_trace(stages: Sequence[Stage]) -> list[list[str]]:
    if len(stages) != 6:
        return []
    selected = [_choice_goal(stage, "R") for stage in stages]
    return [
        [
            "S",
            *(choice for choice, _goal, _bound in selected),
            *(goal for _choice, goal, _bound in reversed(selected)),
            "E",
        ]
    ]


def deterministic_groups(stages: Sequence[Stage]) -> dict[str, list[list[str]]]:
    groups = {"branch_assignments": branch_assignment_traces(stages)}
    if not stages:
        return groups
    groups.update(
        {
            "deadline_exact": deadline_boundary_traces(stages, difference_offset=0),
            "deadline_plus_one": deadline_boundary_traces(stages, difference_offset=1),
            "missing_decision": missing_decision_traces(stages),
            "both_branches": both_branches_traces(stages),
            "decision_order_violation": decision_order_violation_traces(stages),
            "missing_selected_goal": missing_selected_goal_traces(stages),
            "wrong_goal_only": wrong_goal_only_traces(stages),
            "goal_before_choice": goal_before_choice_traces(stages),
            "end_too_early": end_too_early_traces(stages),
            "goal_reordering": goal_reordering_traces(stages),
        }
    )
    if len(stages) == 6:
        groups["full_reverse_infeasible"] = infeasible_full_reverse_trace(stages)
    return groups


def _random_positive_trace(
    stages: Sequence[Stage], rng: random.Random
) -> tuple[list[str], list[str], list[str]]:
    branches = [rng.choice("LR") for _stage in stages]
    selected = [_choice_goal(stage, branch) for stage, branch in zip(stages, branches)]
    choices = [item[0] for item in selected]
    goals = [item[1] for item in selected]
    bounds = [item[2] for item in selected]
    indices = list(range(len(stages)))
    for _attempt in range(100):
        rng.shuffle(indices)
        positions = {
            goal_index: len(stages) + 1 + rank
            for rank, goal_index in enumerate(indices)
        }
        if all(
            1 <= positions[index] - (index + 1) <= bounds[index]
            for index in range(len(stages))
        ):
            break
    else:  # pragma: no cover - canonical order is always feasible
        indices = list(range(len(stages)))
    trace = ["S", *choices, *(goals[index] for index in indices), "E"]

    # Add a few irrelevant events only where every selected deadline stays valid.
    for _ in range(rng.randint(0, 2)):
        insertion = rng.randint(1, len(trace) - 1)
        candidate = [*trace[:insertion], "O", *trace[insertion:]]
        choice_positions = {choice: candidate.index(choice) for choice in choices}
        goal_positions = {goal: candidate.index(goal) for goal in goals}
        if all(
            1 <= goal_positions[goal] - choice_positions[choice] <= bound
            for choice, goal, bound in selected
        ):
            trace = candidate
    return trace, choices, goals


def structured_random_traces(
    stages: Sequence[Stage], *, count: int, seed: int
) -> list[list[str]]:
    if not stages:
        return []
    rng = random.Random(seed)
    traces = []
    for sample in range(count):
        trace, choices, goals = _random_positive_trace(stages, rng)
        mode = sample % 6
        target = rng.randrange(len(stages))
        if mode == 1:  # missing selected goal
            trace.remove(goals[target])
        elif mode == 2:  # selected goal beyond its deadline
            choice = choices[target]
            goal = goals[target]
            stage = stages[target]
            bound = (
                stage.left_bound if choice == stage.left_event else stage.right_bound
            )
            trace.remove(goal)
            insert_after = trace.index(choice) + bound + 1
            while len(trace) <= insert_after:
                trace.insert(-1, "O")
            trace.insert(insert_after, goal)
        elif mode == 3:  # early end
            trace.remove("E")
            trace.insert(trace.index(goals[target]), "E")
        elif mode == 4:
            if len(stages) > 1:  # decision-order violation
                first = rng.randrange(len(stages) - 1)
                p1 = trace.index(choices[first])
                p2 = trace.index(choices[first + 1])
                trace[p1], trace[p2] = trace[p2], trace[p1]
            else:  # both branches for the single stage
                opposite = (
                    stages[0].right_event
                    if choices[0] == stages[0].left_event
                    else stages[0].left_event
                )
                trace.insert(trace.index(choices[0]) + 1, opposite)
        elif mode == 5:  # wrong goal only
            stage = stages[target]
            wrong = (
                stage.right_goal
                if choices[target] == stage.left_event
                else stage.left_goal
            )
            trace[trace.index(goals[target])] = wrong
        traces.append(trace)
    return traces


def flattened_deterministic_traces(stages: Sequence[Stage]) -> list[list[str]]:
    return [trace for group in deterministic_groups(stages).values() for trace in group]


def branch_rewire_probe_traces(
    stages: Sequence[Stage], stage_index: int
) -> list[list[str]]:
    stage = stages[stage_index - 1]
    branches = ["L"] * len(stages)
    old_goal_trace = canonical_trace(stages, branches)
    new_goal_trace = list(old_goal_trace)
    new_goal_trace[new_goal_trace.index(stage.left_goal)] = f"X{stage_index}"
    right_branches = ["L"] * len(stages)
    right_branches[stage_index - 1] = "R"
    right_trace = canonical_trace(stages, right_branches)
    return [old_goal_trace, new_goal_trace, right_trace]
