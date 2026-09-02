from __future__ import annotations

import pytest

from a1_ltlf import FormulaSyntaxError, evaluate, format_formula, parse_formula


def trace(*steps: str) -> tuple[frozenset[str], ...]:
    return tuple(frozenset(step.split("+")) if step else frozenset() for step in steps)


def test_standard_future_operators() -> None:
    sample = trace("A", "", "B")
    assert evaluate(parse_formula("F at_B"), sample)
    assert evaluate(parse_formula("G !at_X"), sample)
    assert evaluate(parse_formula("at_A -> X X at_B"), sample)
    assert evaluate(parse_formula("!at_X U at_B"), sample)


def test_next_is_strong() -> None:
    assert not evaluate(parse_formula("X at_A"), trace("A"))


def test_until_allows_forbidden_label_at_endpoint() -> None:
    assert evaluate(parse_formula("!at_X U at_C"), trace("A", "X+C"))
    assert not evaluate(parse_formula("!at_X U at_C"), trace("X", "C"))


def test_canonical_round_trip() -> None:
    formula = parse_formula("G(at_A -> (X at_B | X X at_B))")
    assert parse_formula(format_formula(formula)) == formula


@pytest.mark.parametrize(
    "source",
    ("", "COUNT_AT_MOST(at_X,2)", "at_A && at_B", "F[1,4] at_B", "at_A extra"),
)
def test_nonstandard_or_malformed_syntax_is_rejected(source: str) -> None:
    with pytest.raises(FormulaSyntaxError):
        parse_formula(source)
