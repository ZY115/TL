"""Focused semantic and canonical-representation tests for Pilot 0.3."""

from __future__ import annotations

import pytest

from src.explicit_conditional.generator import compile_monitor, generate_source
from src.model import stages_for_k, with_left_goal_rewired
from src.oracle import branch_timing_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parse_parameter_source,
)
from src.tl.evaluator import evaluate as evaluate_tl
from src.tl.generator import task_formula
from src.traces import (
    branch_rewire_probe_traces,
    deterministic_groups,
    infeasible_full_reverse_trace,
)


def _three_results(
    trajectory: list[str], stages: tuple[object, ...]
) -> tuple[bool, ...]:
    formula = task_formula(stages)  # type: ignore[arg-type]
    explicit = compile_monitor(generate_source(stages))  # type: ignore[arg-type]
    parameter_stages = parse_parameter_source(
        canonical_parameter_source(stages)  # type: ignore[arg-type]
    )
    return (
        evaluate_tl(formula, trajectory),
        bool(explicit(trajectory)),
        evaluate_parameterized(trajectory, parameter_stages),
    )


@pytest.mark.parametrize("k", range(7))
def test_all_deterministic_groups_match_oracle(k: int) -> None:
    stages = stages_for_k(k)
    for traces in deterministic_groups(stages).values():
        for trajectory in traces:
            expected = branch_timing_oracle(trajectory, stages)
            assert _three_results(trajectory, stages) == (expected, expected, expected)


def test_inclusive_left_and_right_deadlines() -> None:
    stage = stages_for_k(1)
    cases = [
        (["S", "L1", *("O" for _ in range(7)), "P1", "E"], True),
        (["S", "L1", *("O" for _ in range(8)), "P1", "E"], False),
        (["S", "R1", *("O" for _ in range(9)), "Q1", "E"], True),
        (["S", "R1", *("O" for _ in range(10)), "Q1", "E"], False),
    ]
    for trajectory, expected in cases:
        assert branch_timing_oracle(trajectory, stage) is expected
        assert _three_results(trajectory, stage) == (expected, expected, expected)


def test_unselected_goal_is_irrelevant() -> None:
    stages = stages_for_k(1)
    trajectory = ["S", "Q1", "L1", "P1", "E"]
    assert branch_timing_oracle(trajectory, stages)
    assert _three_results(trajectory, stages) == (True, True, True)


def test_k6_full_reverse_is_a_deadline_failure() -> None:
    stages = stages_for_k(6)
    trajectory = infeasible_full_reverse_trace(stages)[0]
    assert trajectory.index("Q1") - trajectory.index("R1") == 11
    assert not branch_timing_oracle(trajectory, stages)
    assert _three_results(trajectory, stages) == (False, False, False)


def test_rewire_changes_only_the_selected_left_goal_semantics() -> None:
    original = stages_for_k(3)
    modified = with_left_goal_rewired(original, 2)
    old_goal, new_goal, right_branch = branch_rewire_probe_traces(original, 2)
    assert not branch_timing_oracle(old_goal, modified)
    assert branch_timing_oracle(new_goal, modified)
    assert branch_timing_oracle(right_branch, modified)
    for trajectory in (old_goal, new_goal, right_branch):
        expected = branch_timing_oracle(trajectory, modified)
        assert _three_results(trajectory, modified) == (expected, expected, expected)
