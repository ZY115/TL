from __future__ import annotations

from src.oracle import sequence_oracle
from src.traces import RANDOM_CATEGORY_COUNTS, randomized_trace_groups


def test_randomized_groups_are_reproducible_and_total_20000() -> None:
    targets = ["A1", "A2", "A3", "A4", "A5"]
    first = list(randomized_trace_groups(targets, 12345))
    second = list(randomized_trace_groups(targets, 12345))
    assert first == second
    assert sum(len(traces) for _name, _seed, traces in first) == 20_000
    assert {name: len(traces) for name, _seed, traces in first} == (
        RANDOM_CATEGORY_COUNTS
    )


def test_constructed_categories_cover_positive_and_negative_behavior() -> None:
    targets = ["A1", "A2", "A3", "A4", "A5"]
    groups = {
        name: traces for name, _seed, traces in randomized_trace_groups(targets, 67890)
    }
    assert all(sequence_oracle(trace, targets) for trace in groups["satisfying"])
    assert not any(sequence_oracle(trace, targets) for trace in groups["incomplete"])
    for category in ("early_future", "repeated", "irrelevant"):
        outcomes = {sequence_oracle(trace, targets) for trace in groups[category]}
        assert outcomes == {False, True}
