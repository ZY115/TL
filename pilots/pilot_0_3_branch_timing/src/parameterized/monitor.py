"""Canonical configuration and reusable conditional deadline engine."""

from __future__ import annotations

import ast
from collections.abc import Sequence

import black

from ..model import Stage
from ..tree_diff import TreeNode


def canonical_parameter_source(stages: Sequence[Stage]) -> str:
    if not stages:
        return "STAGES = []\n"
    lines = ["STAGES = ["]
    for stage in stages:
        fields = ", ".join(repr(field) for field in stage.fields())
        lines.append(f"    ({fields}),")
    lines.append("]")
    lines.append("")
    return black.format_str("\n".join(lines), mode=black.Mode(line_length=88))


def parse_parameter_source(source: str) -> tuple[Stage, ...]:
    module = ast.parse(source)
    if len(module.body) != 1 or not isinstance(module.body[0], ast.Assign):
        raise ValueError("Expected one STAGES assignment")
    rows = ast.literal_eval(module.body[0].value)
    return tuple(
        Stage(
            index=index,
            left_event=row[0],
            left_goal=row[1],
            left_bound=row[2],
            right_event=row[3],
            right_goal=row[4],
            right_bound=row[5],
        )
        for index, row in enumerate(rows, start=1)
    )


def evaluate_parameterized(trajectory: Sequence[str], stages: Sequence[Stage]) -> bool:
    if not trajectory or trajectory[0] != "S":
        return False

    expected_stage = 1
    selected: dict[int, tuple[str, int, int]] = {}
    completed: set[int] = set()
    seen_named: set[str] = set()
    choice_lookup = {
        event: (stage.index, goal, bound)
        for stage in stages
        for event, goal, bound in (
            (stage.left_event, stage.left_goal, stage.left_bound),
            (stage.right_event, stage.right_goal, stage.right_bound),
        )
    }
    goal_lookup = {
        goal: stage.index
        for stage in stages
        for goal in (stage.left_goal, stage.right_goal)
    }

    for step, event in enumerate(trajectory):
        if event != "O":
            if event in seen_named:
                return False
            seen_named.add(event)
        if event == "E":
            return expected_stage == len(stages) + 1 and len(completed) == len(stages)
        if event in choice_lookup:
            stage_index, goal, bound = choice_lookup[event]
            if stage_index != expected_stage:
                return False
            selected[stage_index] = (goal, bound, step)
            expected_stage += 1
        elif event in goal_lookup:
            stage_index = goal_lookup[event]
            if stage_index in selected and selected[stage_index][0] == event:
                _goal, bound, start = selected[stage_index]
                if not 1 <= step - start <= bound:
                    return False
                completed.add(stage_index)
    return False


def parameter_tree(stages: Sequence[Stage]) -> TreeNode:
    stage_nodes = []
    for stage in stages:
        stage_nodes.append(
            TreeNode(
                f"Stage:{stage.index}",
                (
                    TreeNode(
                        "Left",
                        (
                            TreeNode(f"Event:{stage.left_event}"),
                            TreeNode(f"Goal:{stage.left_goal}"),
                            TreeNode(f"Bound:{stage.left_bound}"),
                        ),
                    ),
                    TreeNode(
                        "Right",
                        (
                            TreeNode(f"Event:{stage.right_event}"),
                            TreeNode(f"Goal:{stage.right_goal}"),
                            TreeNode(f"Bound:{stage.right_bound}"),
                        ),
                    ),
                ),
            )
        )
    return TreeNode("Task", (TreeNode("Stages", tuple(stage_nodes)),))


def parameter_structural_metrics(stages: Sequence[Stage]) -> dict[str, int]:
    k = len(stages)
    return {
        "parameter_stage_count": k,
        "parameter_branch_count": 2 * k,
        "parameter_goal_mapping_count": 2 * k,
        "parameter_bound_count": 2 * k,
        "parameter_task_fields": 6 * k,
    }
