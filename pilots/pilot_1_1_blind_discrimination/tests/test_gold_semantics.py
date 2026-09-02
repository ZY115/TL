from __future__ import annotations

import random

from a1_ltlf import evaluate
from coordinator_private.build_training_gold import tasks
from coordinator_private.oracle.ltlf_gold import compile_task
from coordinator_private.oracle.semantics import evaluate_task


def test_training_gold_is_expressible_in_fixed_a1() -> None:
    rng = random.Random(20_261_101)
    alphabet = ("A", "B", "C", "D", "X")
    for task in tasks():
        formula = compile_task(task)
        for _ in range(2_000):
            sample = tuple(
                frozenset({rng.choice(alphabet)}) for _ in range(rng.randint(1, 14))
            )
            assert evaluate(formula, sample) == evaluate_task(task, sample)
