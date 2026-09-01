"""Reusable sequence-monitor engine and task-specific list serialization."""

from __future__ import annotations

import ast
from collections.abc import Sequence

import black

from src.tree_diff import TreeNode


def evaluate_parameterized(trajectory: Sequence[str], targets: Sequence[str]) -> bool:
    """Evaluate an ordered target list with a reusable index monitor."""

    index = 0
    for event in trajectory:
        if index < len(targets) and event == targets[index]:
            index += 1
    return index == len(targets)


def canonical_parameter_source(targets: Sequence[str]) -> str:
    """Serialize the counted task-specific target list with Black."""

    raw = f"targets = {list(targets)!r}\n"
    return black.format_str(raw, mode=black.Mode(line_length=88))


def parse_parameter_source(source: str) -> list[str]:
    """Read the exact generated task-specific configuration."""

    module = ast.parse(source)
    if len(module.body) != 1 or not isinstance(module.body[0], ast.Assign):
        raise ValueError("Expected one targets assignment")
    assignment = module.body[0]
    if len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name):
        raise ValueError("Expected a simple targets assignment")
    if assignment.targets[0].id != "targets":
        raise ValueError("Expected assignment to targets")
    value = ast.literal_eval(assignment.value)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("targets must be a list of strings")
    return value


def parameter_tree(targets: Sequence[str]) -> TreeNode:
    """Return the normalized parameter tree counted by edit distance."""

    return TreeNode("Sequence", tuple(TreeNode(target) for target in targets))
