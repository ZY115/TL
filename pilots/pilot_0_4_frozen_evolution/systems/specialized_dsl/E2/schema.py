"""E2 schema with reusable branch-post sequences."""

from __future__ import annotations

import ast

ALLOWED_SECTIONS = ("STAGES", "GLOBAL_AVOID", "BRANCH_POST_SEQUENCES")


def parse_task(source: str) -> dict[str, object]:
    values: dict[str, object] = {
        "STAGES": [],
        "GLOBAL_AVOID": [],
        "BRANCH_POST_SEQUENCES": [],
    }
    for statement in ast.parse(source).body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            raise ValueError("Task source must contain simple assignments")
        target = statement.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ALLOWED_SECTIONS:
            raise ValueError("Unsupported schema section")
        values[target.id] = ast.literal_eval(statement.value)
    return values
