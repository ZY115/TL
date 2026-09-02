"""The design-C adapter is admissible only if it matches the frozen interpreter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import ltlf_dfa as L  # noqa: E402
from src.adapters import design_c as adapter  # noqa: E402
from src.blackbox import load_dsl_c  # noqa: E402
from coordinator_private.validate_a2_training import conformance_traces  # noqa: E402

PILOT_1_2 = Path(__file__).resolve().parents[2] / "pilot_1_2_compositional_audit"

SOURCES = [
    "order(A, B)",
    "and(visit(A), every(A, within(B, 1, 2)))",
    "every(A, within(B, 1, 1))",
    "and(order(A, B, C), avoid_until(X, C))",
    "every(A, within(B, 1, 2, then=avoid_until(X, C)))",
    "or(order(A, C), order(D, C))",
    "visit(any(B, D))",
    "avoid(any(X, D))",
    "order(any(A, D), C)",
    "avoid_until(any(X, D), C)",
    "avoid_until(X, any(C, D))",
    "every(any(A, B), visit(C))",
    "and(visit(A), every(A, within(B, 1, 2, then=visit(C))), every(C, avoid_until(X, D)))",
]
SOURCES += [
    path.read_text(encoding="utf-8")
    for path in sorted((PILOT_1_2 / "a2_designs/design_c/training_artifacts").glob("*"))
]


@pytest.mark.parametrize("source", SOURCES)
def test_adapter_agrees_with_interpreter(source: str) -> None:
    interpreter = load_dsl_c(source)
    formula = adapter.to_ltlf(source)
    for _category, trace in conformance_traces():
        assert interpreter(trace) == L.evaluate(formula, trace), (source, trace)


def test_requirement_units_follow_top_level_and() -> None:
    assert len(adapter.requirements("and(order(A, B, C), avoid_until(X, C))")) == 2
    assert len(adapter.requirements("order(A, B)")) == 1
