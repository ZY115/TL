"""Systematic Pilot 0.2 trace generation."""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence


def trace_from_gaps(targets: Sequence[str], gaps: Sequence[int]) -> tuple[str, ...]:
    if len(gaps) != len(targets) - 1:
        raise ValueError("Expected one gap between every adjacent target pair")
    trace: list[str] = [targets[0]]
    for gap, target in zip(gaps, targets[1:], strict=True):
        trace.extend(["O"] * gap)
        trace.append(target)
    return tuple(trace)


def gap_enumeration_traces(targets: Sequence[str]) -> Iterator[tuple[str, ...]]:
    for gaps in itertools.product((0, 1, 2), repeat=len(targets) - 1):
        yield trace_from_gaps(targets, gaps)


def missing_target_traces(targets: Sequence[str]) -> list[tuple[str, ...]]:
    return [
        tuple(target for target in targets if target != missing) for missing in targets
    ]


def adjacent_swap_traces(targets: Sequence[str]) -> list[tuple[str, ...]]:
    traces: list[tuple[str, ...]] = []
    for index in range(len(targets) - 1):
        swapped = list(targets)
        swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
        traces.append(tuple(swapped))
    return traces
