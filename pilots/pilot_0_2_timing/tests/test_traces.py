from __future__ import annotations

from src.model import BASE_TARGETS
from src.traces import (
    adjacent_swap_traces,
    gap_enumeration_traces,
    missing_target_traces,
    trace_from_gaps,
)


def test_gap_enumeration_has_exactly_3_to_the_9_traces() -> None:
    traces = list(gap_enumeration_traces(BASE_TARGETS))
    assert len(traces) == 19_683
    assert len(set(traces)) == 19_683


def test_gap_position_difference_formula() -> None:
    gaps = (1, 0, 2, 1, 0, 2, 1, 0, 2)
    trace = trace_from_gaps(BASE_TARGETS, gaps)
    positions = {event: index for index, event in enumerate(trace) if event != "O"}
    for j in range(5):
        assert positions[f"A{j + 6}"] - positions[f"A{j + 1}"] == 5 + sum(
            gaps[j : j + 5]
        )


def test_sequence_failure_counts() -> None:
    missing = missing_target_traces(BASE_TARGETS)
    swapped = adjacent_swap_traces(BASE_TARGETS)
    assert len(missing) == 10
    assert len(swapped) == 9
    assert all(len(set(trace)) == len(trace) for trace in [*missing, *swapped])
