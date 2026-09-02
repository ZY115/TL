"""The progression automaton must agree with the reference evaluator exactly."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import ltlf_dfa as L  # noqa: E402
from src.blackbox import enumerate_traces  # noqa: E402
from coordinator_private.build_audit_gold import gold_tasks  # noqa: E402
from coordinator_private.build_training_gold import tasks as training_tasks  # noqa: E402
from coordinator_private.oracle.ltlf_gold import compile_task  # noqa: E402

AUTHORED = [
    "F (at_A & X F at_B)",
    "G !at_X",
    "F at_A & G (at_A -> (X at_B | X X at_B))",
    "F at_A & G (at_A -> (X (at_B & F at_C) | X X (at_B & F at_C)))",
    "!at_X U at_C",
    "F (at_A & X F (at_B & X F at_C)) & (!at_X U at_C)",
    "G (at_A -> (X (at_B & (!at_X U at_C)) | X X (at_B & (!at_X U at_C))))",
    "X (G at_A)",
    "!(X at_A)",
    "!(at_A U at_B)",
    "X X X at_B | X at_B",
]


def _random_traces(n: int, seed: int):
    rng = random.Random(seed)
    for _ in range(n):
        yield tuple(
            frozenset(rng.sample(L.paths.LABELS, rng.choices((0, 1, 2), (1, 6, 2))[0]))
            for _ in range(rng.randint(0, 10))
        )


@pytest.mark.parametrize("text", AUTHORED)
def test_progression_matches_reference_on_authored_formulas(text: str) -> None:
    f = L.parse_formula(text)
    dfa = L.build_dfa(f)
    for trace in list(enumerate_traces(5)) + list(_random_traces(3000, hash(text) % 10_000)):
        assert L.evaluate(f, trace) == L.evaluate_by_progression(f, trace) == dfa.run(trace), trace


@pytest.mark.parametrize("task", [*training_tasks(), *gold_tasks()], ids=lambda t: t.id)
def test_gold_formulas_build_and_agree(task) -> None:
    f = compile_task(task)
    dfa = L.build_dfa(f)
    assert len(dfa.states) < 5_000, task.id
    for trace in _random_traces(2000, 77):
        assert L.evaluate(f, trace) == dfa.run(trace)


def test_strong_next_rejects_a_trace_that_ends() -> None:
    f = L.parse_formula("X (G at_A)")
    assert L.build_dfa(f).run((frozenset({"A"}),)) is False
    assert L.build_dfa(f).run((frozenset({"A"}), frozenset({"A"}))) is True


def test_empty_trace_semantics() -> None:
    assert L.build_dfa(L.parse_formula("G !at_X")).run(()) is True
    assert L.build_dfa(L.parse_formula("F at_A")).run(()) is False


def test_satisfiability_and_witness() -> None:
    sat, witness = L.satisfiable(L.parse_formula("F at_A & G !at_A"))
    assert sat is False and witness is None
    sat, witness = L.satisfiable(L.parse_formula("F (at_A & X F at_B)"))
    assert sat is True and witness is not None
    assert L.evaluate(L.parse_formula("F (at_A & X F at_B)"), witness)
    assert len(witness) == 2


def test_inclusion_and_relation() -> None:
    a, b = L.parse_formula("F at_A"), L.parse_formula("F at_A | F at_B")
    assert L.includes(a, b)[0] is True
    ok, counter = L.includes(b, a)
    assert ok is False and L.evaluate(b, counter) and not L.evaluate(a, counter)
    assert L.relation(a, b)[0] == "strictly_weaker"
    assert L.relation(b, a)[0] == "strictly_stronger"
    assert L.relation(a, a)[0] == "equivalent"
    c = L.parse_formula("F at_C")
    assert L.relation(a, c)[0] == "incomparable"


def test_conjunct_decomposition_recovers_requirements() -> None:
    f = L.parse_formula("F at_A & G (at_A -> X at_B) & (!at_X U at_C)")
    assert len(L.conjuncts(f)) == 3
