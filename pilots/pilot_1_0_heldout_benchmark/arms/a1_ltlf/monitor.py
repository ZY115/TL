"""Independent A1 evaluator and project-owned DFA synthesis boundary."""

from __future__ import annotations

import operator
import time
from dataclasses import dataclass, field

from environments.warehouse import TraceStep

from .syntax import (
    Always,
    And,
    Atom,
    CountAtMostFormula,
    Eventually,
    Formula,
    Implies,
    Next,
    Not,
    OnceFormula,
    Or,
    PriorityFormula,
    ResourceComparison,
    SinceFormula,
    Until,
)

COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def evaluate_formula(
    formula: Formula, trace: tuple[TraceStep, ...], position: int = 0
) -> bool:
    if isinstance(formula, Atom):
        return position < len(trace) and formula.name in trace[position].propositions
    if isinstance(formula, ResourceComparison):
        return position < len(trace) and COMPARISONS[formula.operator](
            trace[position].resource(formula.resource), formula.value
        )
    if isinstance(formula, Not):
        return not evaluate_formula(formula.operand, trace, position)
    if isinstance(formula, And):
        return all(evaluate_formula(item, trace, position) for item in formula.operands)
    if isinstance(formula, Or):
        return any(evaluate_formula(item, trace, position) for item in formula.operands)
    if isinstance(formula, Next):
        return position + 1 < len(trace) and evaluate_formula(
            formula.operand, trace, position + 1
        )
    if isinstance(formula, Eventually):
        return any(
            evaluate_formula(formula.operand, trace, index)
            for index in range(position, len(trace))
        )
    if isinstance(formula, Always):
        return all(
            evaluate_formula(formula.operand, trace, index)
            for index in range(position, len(trace))
        )
    if isinstance(formula, Until):
        return any(
            evaluate_formula(formula.right, trace, end)
            and all(
                evaluate_formula(formula.left, trace, index)
                for index in range(position, end)
            )
            for end in range(position, len(trace))
        )
    if isinstance(formula, Implies):
        return not evaluate_formula(
            formula.antecedent, trace, position
        ) or evaluate_formula(formula.consequent, trace, position)
    if isinstance(formula, CountAtMostFormula):
        return (
            sum(
                evaluate_formula(formula.atom, trace, index)
                for index in range(position, len(trace))
            )
            <= formula.maximum
        )
    if isinstance(formula, OnceFormula):
        return any(
            evaluate_formula(formula.atom, trace, index)
            for index in range(position + 1)
        )
    if isinstance(formula, SinceFormula):
        landmark = next(
            (
                index
                for index in range(position, -1, -1)
                if evaluate_formula(formula.landmark, trace, index)
            ),
            None,
        )
        return landmark is not None and all(
            evaluate_formula(formula.condition, trace, index)
            for index in range(landmark, position + 1)
        )
    if isinstance(formula, PriorityFormula):
        return any(evaluate_formula(item, trace, position) for item in formula.options)
    raise TypeError(type(formula))


Symbol = tuple[tuple[str, ...], tuple[tuple[str, int], ...]]
State = tuple[Symbol, ...]


@dataclass(slots=True)
class DFA:
    formula: Formula
    horizon: int = 40
    state_budget: int = 1_000_000
    timeout_seconds: float = 60.0
    initial: State = ()
    states: set[State] = field(default_factory=lambda: {()})
    accepting: set[State] = field(default_factory=set)
    transitions: dict[tuple[State, Symbol], State] = field(default_factory=dict)
    _start: float = field(default_factory=time.monotonic)

    def _step(self, state: State, step: TraceStep) -> State:
        symbol = tuple(sorted(step.propositions)), tuple(sorted(step.resources))
        key = state, symbol
        if key not in self.transitions:
            if len(state) >= self.horizon:
                raise ValueError("A1 trace exceeds H")
            if len(self.states) >= self.state_budget:
                raise RuntimeError("synthesis_timeout: state budget")
            if time.monotonic() - self._start > self.timeout_seconds:
                raise RuntimeError("synthesis_timeout: 60 s")
            self.transitions[key] = (*state, symbol)
            self.states.add(self.transitions[key])
        return self.transitions[key]

    def accepts(self, trace: tuple[TraceStep, ...]) -> bool:
        state = self.initial
        for step in trace:
            state = self._step(state, step)
        reconstructed = tuple(
            TraceStep(frozenset(propositions), resources)
            for propositions, resources in state
        )
        accepted = evaluate_formula(self.formula, reconstructed)
        if accepted:
            self.accepting.add(state)
        return accepted


def compile_ltlf(
    formula: Formula,
    *,
    horizon: int = 40,
    state_budget: int = 1_000_000,
    timeout_seconds: float = 60.0,
) -> DFA:
    return DFA(formula, horizon, state_budget, timeout_seconds)
