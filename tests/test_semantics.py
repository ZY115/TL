from __future__ import annotations

import itertools

import pytest

from src.explicit_fsm.generator import compile_monitor, generate_source
from src.oracle import sequence_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parse_parameter_source,
)
from src.tl.evaluator import evaluate
from src.tl.generator import sequence_formula


@pytest.mark.parametrize(
    ("trajectory", "expected"),
    [
        (["O", "A1", "O", "A2", "O", "A3"], True),
        (["A1", "A1", "A2", "A2", "A3"], True),
        (["A2", "A1", "A2", "A3"], True),
        (["A2", "A1", "A3"], False),
        ([], False),
        (["A1", "A2"], False),
    ],
)
def test_authoritative_examples(trajectory: list[str], expected: bool) -> None:
    targets = ["A1", "A2", "A3"]
    assert sequence_oracle(trajectory, targets) is expected


@pytest.mark.parametrize("n", [1, 2, 3])
def test_all_representations_match_oracle_exhaustively(n: int) -> None:
    targets = [f"A{index}" for index in range(1, n + 1)]
    alphabet = ["O", *targets]
    formula = sequence_formula(targets)
    fsm = compile_monitor(generate_source(targets))
    parameter_targets = parse_parameter_source(canonical_parameter_source(targets))

    for length in range(n + 3):
        for trajectory in itertools.product(alphabet, repeat=length):
            expected = sequence_oracle(trajectory, targets)
            assert evaluate(formula, trajectory) is expected
            assert fsm(trajectory) is expected
            assert evaluate_parameterized(trajectory, parameter_targets) is expected


def test_empty_trace_is_false_for_single_target() -> None:
    assert not evaluate(sequence_formula(["A1"]), [])
    assert not compile_monitor(generate_source(["A1"]))([])
    assert not evaluate_parameterized([], ["A1"])
