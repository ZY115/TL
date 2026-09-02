"""E0 specialized-DSL parser/interpreter composition."""

from __future__ import annotations

from collections.abc import Sequence

from .interpreter import evaluate
from .schema import parse_task


def evaluate_task(source: str, trajectory: Sequence[str]) -> bool:
    return evaluate(parse_task(source), trajectory)
