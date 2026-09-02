"""Frozen E0 Macro-TL task compiler with generic RULE composition."""

from __future__ import annotations

import re
from functools import reduce

from .evaluator import evaluate
from .macro import Stage, build_base_formula
from .parser import parse_rule
from .syntax import And, Formula

STAGE_PATTERN = re.compile(
    r"TIMED_CHOICE_STAGE\("
    r"([A-Za-z_][A-Za-z_0-9]*), ([A-Za-z_][A-Za-z_0-9]*), (\d+), "
    r"([A-Za-z_][A-Za-z_0-9]*), ([A-Za-z_][A-Za-z_0-9]*), (\d+)\)"
)


def _argument(line: str, macro: str) -> str:
    match = re.fullmatch(rf"{macro}\(([A-Za-z_][A-Za-z_0-9]*)\)", line)
    if match is None:
        raise ValueError(f"Invalid {macro} source")
    return match.group(1)


def compile_task(source: str) -> Formula:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    start = _argument(lines[0], "START")
    end_index = next(
        index for index, line in enumerate(lines) if line.startswith("END(")
    )
    end = _argument(lines[end_index], "END")
    stages = []
    for line in lines:
        match = STAGE_PATTERN.fullmatch(line)
        if match:
            stages.append(
                Stage(
                    len(stages) + 1,
                    match.group(1),
                    match.group(2),
                    int(match.group(3)),
                    match.group(4),
                    match.group(5),
                    int(match.group(6)),
                )
            )
    formulae = [build_base_formula(start, end, tuple(stages))]
    formulae.extend(parse_rule(line[5:]) for line in lines if line.startswith("RULE "))
    return reduce(And, formulae)


def evaluate_task(source: str, trajectory: list[str]) -> bool:
    return evaluate(compile_task(source), trajectory)
