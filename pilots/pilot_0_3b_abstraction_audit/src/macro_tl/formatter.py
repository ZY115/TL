"""Deterministic Macro-TL surface formatter."""

from __future__ import annotations

from .syntax import MacroTask


def format_macro_tl(task: MacroTask) -> str:
    lines = [f"START({task.start})"]
    if task.stages:
        lines.append("ORDERED_CHOICES(")
        for index, stage in enumerate(task.stages):
            suffix = "," if index < len(task.stages) - 1 else ""
            lines.append(f"    ({stage.left_event} | {stage.right_event}){suffix}")
        lines.append(")")
    else:
        lines.append("ORDERED_CHOICES()")
    lines.extend(
        "TIMED_CHOICE_STAGE("
        f"{stage.left_event}, {stage.left_goal}, {stage.left_bound}, "
        f"{stage.right_event}, {stage.right_goal}, {stage.right_bound})"
        for stage in task.stages
    )
    lines.extend([f"END({task.end})", ""])
    return "\n".join(lines)
