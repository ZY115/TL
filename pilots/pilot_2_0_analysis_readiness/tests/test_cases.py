"""The case pool must analyse only artifacts that are known to be correct."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import ltlf_dfa as L  # noqa: E402
from src import queries as Q  # noqa: E402
from src.blackbox import load_dsl_c, load_monitor  # noqa: E402
from src.cases import CORRECT, all_cases  # noqa: E402
from coordinator_private.oracle.semantics import evaluate_task  # noqa: E402
from coordinator_private.validate_a2_training import conformance_traces  # noqa: E402

CASES = all_cases()
TRACES = [t for _c, t in conformance_traces()]


def _every_task():
    for case in CASES:
        yield case
        if case.partner is not None:
            yield case.partner


def test_authored_artifacts_were_verified_correct_in_pilot_1_2() -> None:
    for case in CASES:
        for arm in ("a1", "a2c", "a3"):
            artifact = getattr(case, arm)
            if artifact.source == "authored":
                assert (case.case_id, arm) in CORRECT, (case.case_id, arm)


@pytest.mark.parametrize("case", list(_every_task()), ids=lambda c: c.case_id)
def test_every_artifact_matches_gold_on_the_conformance_corpus(case) -> None:
    a1 = L.parse_formula(case.a1.text)
    a2c = load_dsl_c(case.a2c.text)
    a3 = load_monitor(case.a3.text)
    for trace in TRACES[:6_000]:
        gold = evaluate_task(case.task, trace)
        assert L.evaluate(a1, trace) == gold, ("a1", case.case_id, trace)
        assert a2c(trace) == gold, ("a2c", case.case_id, trace)
        assert a3(trace) == gold, ("a3", case.case_id, trace)


def test_gold_compiled_units_align_with_gold_requirements() -> None:
    for case in _every_task():
        if case.a1.source == "gold_compiled":
            a1_units = [L.key(u) for u in Q.handle(case, "a1").units]
            gold_units = [L.key(u) for u in Q.handle(case, "gold").units]
            assert a1_units == gold_units, case.case_id


def test_pool_composition() -> None:
    classes = {}
    for case in CASES:
        classes[case.case_class] = classes.get(case.case_class, 0) + 1
    assert classes["released"] == 12
    assert classes["inconsistent"] == 4
    assert classes["infeasible"] == 4
    assert classes["redundant"] == 3
    assert classes["vacuous"] == 2
    assert sum(1 for c in CASES if c.partner is not None) == 5
