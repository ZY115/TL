"""Author-facing Macro-TL task syntax and normalized surface tree."""

from __future__ import annotations

from dataclasses import dataclass

from ..model import Stage
from ..tree_diff import TreeNode


@dataclass(frozen=True, slots=True)
class MacroTask:
    start: str
    stages: tuple[Stage, ...]
    end: str


def macro_task(stages: tuple[Stage, ...]) -> MacroTask:
    return MacroTask(start="S", stages=stages, end="E")


def surface_tree(task: MacroTask) -> TreeNode:
    choices = tuple(
        TreeNode(
            "Choice",
            (TreeNode(stage.left_event), TreeNode(stage.right_event)),
        )
        for stage in task.stages
    )
    stage_nodes = tuple(
        TreeNode(
            "TimedChoiceStage",
            (
                TreeNode(f"LeftEvent:{stage.left_event}"),
                TreeNode(f"LeftGoal:{stage.left_goal}"),
                TreeNode(f"LeftBound:{stage.left_bound}"),
                TreeNode(f"RightEvent:{stage.right_event}"),
                TreeNode(f"RightGoal:{stage.right_goal}"),
                TreeNode(f"RightBound:{stage.right_bound}"),
            ),
        )
        for stage in task.stages
    )
    return TreeNode(
        "MacroTask",
        (
            TreeNode(f"Start:{task.start}"),
            TreeNode("OrderedChoices", choices),
            *stage_nodes,
            TreeNode(f"End:{task.end}"),
        ),
    )


def macro_structural_metrics(task: MacroTask) -> dict[str, int]:
    k = len(task.stages)
    return {
        "macro_invocations": k + 3,
        "macro_timed_choice_stage_count": k,
        "macro_ordered_choices_count": 1,
        "macro_arguments": 8 * k + 2,
    }
