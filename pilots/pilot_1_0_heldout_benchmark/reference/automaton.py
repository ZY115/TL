"""Backend-isolated bounded reference automaton with independent semantics."""

from __future__ import annotations

import operator
import time
from dataclasses import dataclass, field
from typing import TypeAlias

from environments.warehouse import TraceStep
from neutral_ir.schema import (
    AllOf,
    Alternative,
    Avoid,
    CountAtMost,
    Deadline,
    Expression,
    MaintainUntil,
    On,
    Once,
    OrderedVisit,
    Priority,
    Since,
    TaskSpec,
    Threshold,
    Visit,
)

Symbol: TypeAlias = tuple[tuple[str, ...], tuple[tuple[str, int], ...]]
State: TypeAlias = tuple[Symbol, ...]
COMPARATORS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


class SynthesisBudgetExceeded(RuntimeError):
    pass


def _symbol(step: TraceStep) -> Symbol:
    return tuple(sorted(step.propositions)), tuple(sorted(step.resources))


def _steps(state: State) -> tuple[TraceStep, ...]:
    return tuple(TraceStep(frozenset(props), resources) for props, resources in state)


def _contains(trace: tuple[TraceStep, ...], position: int, name: str) -> bool:
    return position < len(trace) and name in trace[position].propositions


def _reference_eval(expr: Expression, trace: tuple[TraceStep, ...], start: int) -> bool:
    """Second implementation: deliberately does not import the direct interpreter."""

    if isinstance(expr, Visit):
        return any(expr.event in step.propositions for step in trace[start:])
    if isinstance(expr, Avoid):
        return not any(expr.event in step.propositions for step in trace[start:])
    if isinstance(expr, OrderedVisit):
        wanted = iter(expr.events)
        current = next(wanted, None)
        for step in trace[start:]:
            if current is not None and current in step.propositions:
                current = next(wanted, None)
        return current is None
    if isinstance(expr, Deadline):
        lower = start + expr.lower
        upper = min(start + expr.upper, len(trace) - 1)
        return lower <= upper and any(
            _contains(trace, index, expr.event) for index in range(lower, upper + 1)
        )
    if isinstance(expr, MaintainUntil):
        for index in range(start, len(trace)):
            if _contains(trace, index, expr.goal):
                return True
            if _contains(trace, index, expr.forbidden):
                return False
        return False
    if isinstance(expr, On):
        for index in range(start, len(trace)):
            if _contains(trace, index, expr.trigger) and not _reference_eval(
                expr.obligation, trace, index
            ):
                return False
        return True
    if isinstance(expr, Alternative):
        return any(_reference_eval(option, trace, start) for option in expr.options)
    if isinstance(expr, AllOf):
        return all(
            _reference_eval(requirement, trace, start)
            for requirement in expr.requirements
        )
    if isinstance(expr, CountAtMost):
        count = sum(expr.event in step.propositions for step in trace[start:])
        return count <= expr.maximum
    if isinstance(expr, Once):
        return any(
            expr.event in trace[index].propositions for index in range(start + 1)
        )
    if isinstance(expr, Since):
        last = next(
            (
                index
                for index in range(start, -1, -1)
                if expr.landmark in trace[index].propositions
            ),
            None,
        )
        return last is not None and all(
            expr.condition in trace[index].propositions
            for index in range(last, start + 1)
        )
    if isinstance(expr, Threshold):
        compare = COMPARATORS[expr.operator]
        return all(
            compare(dict(step.resources)[expr.resource], expr.value)
            for step in trace[start:]
        )
    if isinstance(expr, Priority):
        return any(_reference_eval(option, trace, start) for option in expr.options)
    raise TypeError(f"Unsupported reference node: {type(expr)!r}")


@dataclass(slots=True)
class DFA:
    """Project-owned DFA boundary; states are exact bounded trace prefixes."""

    task: TaskSpec
    horizon: int = 40
    state_budget: int = 1_000_000
    timeout_seconds: float = 60.0
    initial: State = ()
    states: set[State] = field(default_factory=lambda: {()})
    accepting: set[State] = field(default_factory=set)
    transitions: dict[tuple[State, Symbol], State] = field(default_factory=dict)
    _started: float = field(default_factory=time.monotonic)

    def transition(self, state: State, step: TraceStep) -> State:
        symbol = _symbol(step)
        key = state, symbol
        if key in self.transitions:
            return self.transitions[key]
        if len(state) >= self.horizon:
            raise ValueError("Trace exceeds fixed horizon")
        if (
            len(self.states) >= self.state_budget
            or time.monotonic() - self._started > self.timeout_seconds
        ):
            raise SynthesisBudgetExceeded(
                "reference automaton state/time budget exceeded"
            )
        result = (*state, symbol)
        self.states.add(result)
        self.transitions[key] = result
        return result

    def is_accepting(self, state: State) -> bool:
        trace = _steps(state)
        accepted = all(
            _reference_eval(requirement.expr, trace, 0)
            for requirement in self.task.requirements
        )
        if accepted:
            self.accepting.add(state)
        return accepted

    def accepts(self, trace: tuple[TraceStep, ...]) -> bool:
        state = self.initial
        for step in trace:
            state = self.transition(state, step)
        return self.is_accepting(state)


def compile_reference_automaton(
    task: TaskSpec,
    *,
    horizon: int = 40,
    state_budget: int = 1_000_000,
    timeout_seconds: float = 60.0,
) -> DFA:
    return DFA(task, horizon, state_budget, timeout_seconds)
