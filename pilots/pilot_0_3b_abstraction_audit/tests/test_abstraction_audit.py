"""Semantic, expansion, and measurement-boundary tests for Pilot 0.3B."""

from __future__ import annotations

import pytest

from run_experiment import PILOT_03, _build_task
from src.core_tl.evaluator import evaluate as evaluate_core_tl
from src.metrics import task_value_occurrences
from src.model import stages_for_k, with_left_goal_rewired
from src.oracle import branch_timing_oracle
from src.parameterized.monitor import evaluate_parameterized
from src.trace_model import task_alphabet, validate_trace_model
from src.traces import (
    branch_rewire_probe_traces,
    deterministic_groups,
    infeasible_full_reverse_trace,
)


@pytest.mark.parametrize("k", range(7))
def test_macro_expands_to_frozen_core_tl(k: int) -> None:
    task = _build_task(stages_for_k(k))
    core = task["core_tl"]
    macro = task["macro_tl"]
    assert macro["formula"] == core["formula"]
    assert macro["formula_v2"] == core["formula"]
    assert macro["expanded_source"] == core["source"]
    reference = PILOT_03 / "generated" / f"B{k}" / "base"
    assert core["source"] == (reference / "formula.btl").read_text(encoding="utf-8")
    assert task["parameterized"]["source"] == (reference / "task_config.py").read_text(
        encoding="utf-8"
    )


def test_shared_trace_validator_externalizes_environment_assumptions() -> None:
    alphabet = task_alphabet(stages_for_k(1))
    assert validate_trace_model(["S", "L1", "P1", "E"], alphabet)
    assert validate_trace_model(["S", "O", "O", "L1", "P1", "E"], alphabet)
    assert not validate_trace_model(["S", "L1", "L1", "P1", "E"], alphabet)
    assert not validate_trace_model(["S", "UNKNOWN", "E"], alphabet)
    assert not validate_trace_model(["S", 3, "E"], alphabet)  # type: ignore[list-item]


@pytest.mark.parametrize("k", range(7))
def test_deterministic_semantics_match_oracle(k: int) -> None:
    stages = stages_for_k(k)
    task = _build_task(stages)
    alphabet = task_alphabet(stages)
    for traces in deterministic_groups(stages).values():
        for trajectory in traces:
            assert validate_trace_model(trajectory, alphabet)
            expected = branch_timing_oracle(trajectory, stages)
            core = evaluate_core_tl(task["core_tl"]["formula"], trajectory)  # type: ignore[arg-type]
            macro = evaluate_core_tl(task["macro_tl"]["formula"], trajectory)  # type: ignore[arg-type]
            explicit = task["explicit"]["monitor"]
            parameter_stages = task["parameterized"]["stages"]
            assert callable(explicit) and isinstance(parameter_stages, tuple)
            assert (
                core,
                macro,
                explicit(trajectory),
                evaluate_parameterized(trajectory, parameter_stages),
            ) == (
                expected,
                expected,
                expected,
                expected,
            )


@pytest.mark.parametrize("k", range(1, 7))
def test_task_value_occurrence_boundary(k: int) -> None:
    stages = stages_for_k(k)
    task = _build_task(stages)
    counts = {
        representation: task_value_occurrences(values["source"], stages)  # type: ignore[arg-type]
        for representation, values in task.items()
    }
    assert counts == {
        "core_tl": 12 * k,
        "macro_tl": 8 * k,
        "explicit": 6 * k,
        "parameterized": 6 * k,
    }


def test_k6_full_reversal_remains_failure() -> None:
    stages = stages_for_k(6)
    trajectory = infeasible_full_reverse_trace(stages)[0]
    assert trajectory.index("Q1") - trajectory.index("R1") == 11
    assert not branch_timing_oracle(trajectory, stages)


def test_rewire_expansion_and_old_goal_probe() -> None:
    original = stages_for_k(4)
    modified = with_left_goal_rewired(original, 2)
    task = _build_task(modified)
    assert task["macro_tl"]["formula"] == task["core_tl"]["formula"]
    old_goal, new_goal, right_goal = branch_rewire_probe_traces(original, 2)
    alphabet = task_alphabet(modified, additional_events=("P2",))
    for trajectory, expected in (
        (old_goal, False),
        (new_goal, True),
        (right_goal, True),
    ):
        assert validate_trace_model(trajectory, alphabet)
        assert branch_timing_oracle(trajectory, modified) is expected


def test_explicit_source_has_no_environment_uniqueness_validator() -> None:
    source = _build_task(stages_for_k(2))["explicit"]["source"]
    assert isinstance(source, str)
    assert "seen_named" not in source
