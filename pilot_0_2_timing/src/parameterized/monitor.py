"""Reusable ordered-sequence and milestone-deadline engine."""

from __future__ import annotations

import ast
from collections.abc import Sequence

import black

from src.model import TimingConstraint
from src.tree_diff import TreeNode


def evaluate_parameterized(
    trajectory: Sequence[str],
    targets: Sequence[str],
    timing_constraints: Sequence[TimingConstraint],
) -> bool:
    """Evaluate a counted target/deadline configuration."""

    target_set = set(targets)
    positions: dict[str, int] = {}
    next_index = 0
    for step, event in enumerate(trajectory):
        if event == "O":
            continue
        if event not in target_set or event in positions:
            return False
        if next_index >= len(targets) or event != targets[next_index]:
            return False
        positions[event] = step
        next_index += 1

    if next_index != len(targets):
        return False
    return all(
        positions[constraint.end] - positions[constraint.start] <= constraint.bound
        for constraint in timing_constraints
    )


def canonical_parameter_source(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> str:
    lines = ["targets = ["]
    lines.extend(f'    "{target}",' for target in targets)
    lines.append("]")
    if timing_constraints:
        lines.append("timing_constraints = [")
        lines.extend(
            f'    ("{constraint.start}", "{constraint.end}", {constraint.bound}),'
            for constraint in timing_constraints
        )
        lines.append("]")
    else:
        lines.append("timing_constraints = []")
    raw = "\n".join(lines) + "\n"
    return black.format_str(raw, mode=black.Mode(line_length=88))


def parse_parameter_source(
    source: str,
) -> tuple[list[str], tuple[TimingConstraint, ...]]:
    module = ast.parse(source)
    assignments: dict[str, object] = {}
    for statement in module.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            raise ValueError("Expected only simple assignments")
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            raise ValueError("Expected name assignment")
        assignments[target.id] = ast.literal_eval(statement.value)

    targets = assignments.get("targets")
    raw_constraints = assignments.get("timing_constraints")
    if not isinstance(targets, list) or not all(
        isinstance(item, str) for item in targets
    ):
        raise ValueError("targets must be a list of strings")
    if not isinstance(raw_constraints, list):
        raise ValueError("timing_constraints must be a list")

    constraints: list[TimingConstraint] = []
    for index, item in enumerate(raw_constraints, start=1):
        if (
            not isinstance(item, tuple)
            or len(item) != 3
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            or not isinstance(item[2], int)
        ):
            raise ValueError("Each timing constraint must be (start, end, bound)")
        constraints.append(
            TimingConstraint(
                name=f"C{index}", start=item[0], end=item[1], bound=item[2]
            )
        )
    return targets, tuple(constraints)


def parameter_tree(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> TreeNode:
    sequence = TreeNode("Sequence", tuple(TreeNode(target) for target in targets))
    timing = TreeNode(
        "Timing",
        tuple(
            TreeNode(
                "Constraint",
                (
                    TreeNode(f"Start:{constraint.start}"),
                    TreeNode(f"End:{constraint.end}"),
                    TreeNode(f"Bound:{constraint.bound}"),
                ),
            )
            for constraint in timing_constraints
        ),
    )
    return TreeNode("Task", (sequence, timing))
