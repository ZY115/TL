"""Generate a canonical explicit conditional timed monitor."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import black

from ..metrics import python_ast_node_count
from ..model import Stage
from ..tree_diff import TreeNode


def generate_source(stages: Sequence[Stage]) -> str:
    lines = [
        "def evaluate(trajectory):",
        '    if not trajectory or trajectory[0] != "S":',
        "        return False",
        "    expected_stage = 1",
        "    success = False",
    ]
    for stage in stages:
        lines.extend(
            [
                f"    selected_{stage.index} = None",
                f"    start_{stage.index} = None",
                f"    done_{stage.index} = False",
            ]
        )
    lines.extend(
        [
            "    for step, event in enumerate(trajectory):",
            '        if event == "E":',
        ]
    )
    completion = " and ".join([f"done_{stage.index}" for stage in stages]) or "True"
    lines.extend(
        [
            f"            success = expected_stage == {len(stages) + 1} and {completion}",
            "            return success",
        ]
    )
    for stage in stages:
        lines.extend(
            [
                f'        elif event == "{stage.left_event}":',
                f"            if expected_stage != {stage.index}:",
                "                return False",
                f'            selected_{stage.index} = "L"',
                f"            start_{stage.index} = step",
                "            expected_stage += 1",
                f'        elif event == "{stage.right_event}":',
                f"            if expected_stage != {stage.index}:",
                "                return False",
                f'            selected_{stage.index} = "R"',
                f"            start_{stage.index} = step",
                "            expected_stage += 1",
                f'        elif event == "{stage.left_goal}" and selected_{stage.index} == "L":',
                f"            if not 1 <= step - start_{stage.index} <= {stage.left_bound}:",
                "                return False",
                f"            done_{stage.index} = True",
                f'        elif event == "{stage.right_goal}" and selected_{stage.index} == "R":',
                f"            if not 1 <= step - start_{stage.index} <= {stage.right_bound}:",
                "                return False",
                f"            done_{stage.index} = True",
            ]
        )
    lines.extend(["    return success", ""])
    return black.format_str("\n".join(lines), mode=black.Mode(line_length=88))


def compile_monitor(source: str) -> Callable[[Sequence[str]], bool]:
    namespace: dict[str, object] = {}
    exec(compile(source, "<explicit_conditional_monitor>", "exec"), namespace)
    monitor = namespace["evaluate"]
    if not callable(monitor):  # pragma: no cover
        raise TypeError("Generated monitor is not callable")
    return monitor  # type: ignore[return-value]


def explicit_tree(stages: Sequence[Stage]) -> TreeNode:
    decision_children = []
    obligation_children = []
    for stage in stages:
        decision_children.append(
            TreeNode(
                f"Stage:{stage.index}",
                (
                    TreeNode(f"LeftChoice:{stage.left_event}"),
                    TreeNode(f"RightChoice:{stage.right_event}"),
                ),
            )
        )
        obligation_children.append(
            TreeNode(
                f"Stage:{stage.index}",
                (
                    TreeNode(f"SelectedVariable:selected_{stage.index}"),
                    TreeNode(f"StartVariable:start_{stage.index}"),
                    TreeNode(f"CompletionFlag:done_{stage.index}"),
                    TreeNode(
                        "LeftBranch",
                        (
                            TreeNode(f"Trigger:{stage.left_event}"),
                            TreeNode(f"Goal:{stage.left_goal}"),
                            TreeNode(f"Bound:{stage.left_bound}"),
                            TreeNode("DeadlineCheck"),
                        ),
                    ),
                    TreeNode(
                        "RightBranch",
                        (
                            TreeNode(f"Trigger:{stage.right_event}"),
                            TreeNode(f"Goal:{stage.right_goal}"),
                            TreeNode(f"Bound:{stage.right_bound}"),
                            TreeNode("DeadlineCheck"),
                        ),
                    ),
                ),
            )
        )
    return TreeNode(
        "ConditionalTimedMonitor",
        (
            TreeNode("DecisionSequence", tuple(decision_children)),
            TreeNode("Obligations", tuple(obligation_children)),
        ),
    )


def explicit_structural_metrics(source: str, stages: Sequence[Stage]) -> dict[str, int]:
    k = len(stages)
    return {
        "explicit_states": k + 2,
        "explicit_transitions": 4 * k + 1,
        "explicit_branches": 4 * k,
        "explicit_conditions": 6 * k + 2,
        "explicit_variables": 3 * k + 2,
        "explicit_selection_variables": k,
        "explicit_timestamp_variables": k,
        "explicit_completion_flags": k,
        "explicit_decision_branches": 2 * k,
        "explicit_goal_branches": 2 * k,
        "explicit_deadline_checks": 2 * k,
        "explicit_numeric_bounds": 2 * k,
        "explicit_branch_mappings": 2 * k,
        "python_ast_nodes": python_ast_node_count(source),
    }


def explicit_stage_add_metrics() -> dict[str, int]:
    return {
        "variables_added": 3,
        "timestamps_added": 1,
        "completion_flags_added": 1,
        "decision_branches_added": 2,
        "goal_checks_added": 2,
    }
