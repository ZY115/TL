"""Parser for the deliberately small deterministic Macro-TL surface language."""

from __future__ import annotations

import re

from ..model import Stage
from .syntax import MacroTask

START_PATTERN = re.compile(r"START\(([A-Za-z_][A-Za-z_0-9]*)\)")
END_PATTERN = re.compile(r"END\(([A-Za-z_][A-Za-z_0-9]*)\)")
CHOICE_PATTERN = re.compile(
    r"\(([A-Za-z_][A-Za-z_0-9]*) \| ([A-Za-z_][A-Za-z_0-9]*)\),?"
)
STAGE_PATTERN = re.compile(
    r"TIMED_CHOICE_STAGE\("
    r"([A-Za-z_][A-Za-z_0-9]*), "
    r"([A-Za-z_][A-Za-z_0-9]*), (\d+), "
    r"([A-Za-z_][A-Za-z_0-9]*), "
    r"([A-Za-z_][A-Za-z_0-9]*), (\d+)\)"
)


def _fullmatch(pattern: re.Pattern[str], text: str) -> re.Match[str]:
    match = pattern.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid Macro-TL syntax: {text!r}")
    return match


def parse_macro_tl(source: str) -> MacroTask:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError("Macro-TL task is incomplete")
    start = _fullmatch(START_PATTERN, lines[0]).group(1)
    end = _fullmatch(END_PATTERN, lines[-1]).group(1)

    cursor = 1
    choices: list[tuple[str, str]] = []
    if lines[cursor] == "ORDERED_CHOICES()":
        cursor += 1
    elif lines[cursor] == "ORDERED_CHOICES(":
        cursor += 1
        while cursor < len(lines) and lines[cursor] != ")":
            match = _fullmatch(CHOICE_PATTERN, lines[cursor])
            choices.append((match.group(1), match.group(2)))
            cursor += 1
        if cursor >= len(lines) or lines[cursor] != ")":
            raise ValueError("ORDERED_CHOICES is not closed")
        cursor += 1
    else:
        raise ValueError("Expected ORDERED_CHOICES")

    stages = []
    while cursor < len(lines) - 1:
        match = _fullmatch(STAGE_PATTERN, lines[cursor])
        stages.append(
            Stage(
                index=len(stages) + 1,
                left_event=match.group(1),
                left_goal=match.group(2),
                left_bound=int(match.group(3)),
                right_event=match.group(4),
                right_goal=match.group(5),
                right_bound=int(match.group(6)),
            )
        )
        cursor += 1

    expected_choices = [(stage.left_event, stage.right_event) for stage in stages]
    if choices != expected_choices:
        raise ValueError("ORDERED_CHOICES does not match stage descriptors")
    return MacroTask(start=start, stages=tuple(stages), end=end)
