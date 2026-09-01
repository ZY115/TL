from __future__ import annotations

import pytest

from src.explicit_timed.generator import compile_monitor, generate_source
from src.model import BASE_TARGETS, constraints_for_m, with_changed_bound
from src.oracle import timed_sequence_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parse_parameter_source,
)
from src.tl.evaluator import evaluate
from src.tl.generator import task_formula
from src.traces import adjacent_swap_traces, missing_target_traces, trace_from_gaps


def _all_results(trace: tuple[str, ...], constraints):
    formula = task_formula(BASE_TARGETS, constraints)
    explicit = compile_monitor(generate_source(BASE_TARGETS, constraints))
    config = canonical_parameter_source(BASE_TARGETS, constraints)
    targets, parsed_constraints = parse_parameter_source(config)
    return (
        evaluate(formula, trace),
        explicit(trace),
        evaluate_parameterized(trace, targets, parsed_constraints),
    )


@pytest.mark.parametrize(
    ("gaps", "expected"),
    [
        ((1, 1, 1, 0, 0, 0, 0, 0, 0), True),
        ((1, 1, 1, 1, 0, 0, 0, 0, 0), False),
    ],
)
def test_inclusive_eight_step_boundary(gaps: tuple[int, ...], expected: bool) -> None:
    trace = trace_from_gaps(BASE_TARGETS, gaps)
    constraints = constraints_for_m(1)
    assert timed_sequence_oracle(trace, BASE_TARGETS, constraints) is expected
    assert _all_results(trace, constraints) == (expected, expected, expected)


def test_numeric_bound_change_changes_semantics_at_seven_steps() -> None:
    gaps = (1, 1, 0, 0, 0, 0, 0, 0, 0)
    trace = trace_from_gaps(BASE_TARGETS, gaps)
    original = constraints_for_m(1)
    modified = with_changed_bound(original, 1, 6)
    assert timed_sequence_oracle(trace, BASE_TARGETS, original)
    assert not timed_sequence_oracle(trace, BASE_TARGETS, modified)
    assert _all_results(trace, modified) == (False, False, False)


@pytest.mark.parametrize("m", range(6))
def test_sequence_failures_are_false_for_every_task(m: int) -> None:
    constraints = constraints_for_m(m)
    failures = [
        *missing_target_traces(BASE_TARGETS),
        *adjacent_swap_traces(BASE_TARGETS),
    ]
    for trace in failures:
        assert not timed_sequence_oracle(trace, BASE_TARGETS, constraints)
        assert _all_results(trace, constraints) == (False, False, False)


@pytest.mark.parametrize("m", range(6))
def test_representative_gap_traces_match_oracle(m: int) -> None:
    constraints = constraints_for_m(m)
    gap_vectors = [
        (0,) * 9,
        (1,) * 9,
        (2,) * 9,
        (0, 1, 2, 0, 1, 2, 0, 1, 2),
        (2, 0, 1, 2, 0, 1, 2, 0, 1),
    ]
    for gaps in gap_vectors:
        trace = trace_from_gaps(BASE_TARGETS, gaps)
        expected = timed_sequence_oracle(trace, BASE_TARGETS, constraints)
        assert _all_results(trace, constraints) == (expected, expected, expected)


def test_oracle_rejects_duplicate_target_as_outside_trace_model() -> None:
    trace = ("A1", "A1", *BASE_TARGETS[1:])
    assert not timed_sequence_oracle(trace, BASE_TARGETS, constraints_for_m(0))
