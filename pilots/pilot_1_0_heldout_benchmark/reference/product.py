"""Bounded existential product search over a deterministic warehouse."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from environments.warehouse import ACTIONS, EnvironmentState, TraceStep, Warehouse

from .automaton import DFA, State, SynthesisBudgetExceeded


@dataclass(frozen=True, slots=True)
class ProductWitness:
    status: str
    actions: tuple[str, ...] = ()
    trace: tuple[TraceStep, ...] = ()
    explored_states: int = 0


def shortest_environment_witness(
    warehouse: Warehouse,
    dfa: DFA,
    *,
    horizon: int = 40,
    expansion_budget: int = 1_000_000,
) -> ProductWitness:
    initial_step = warehouse.trace_step(warehouse.start)
    initial_automaton = dfa.transition(dfa.initial, initial_step)
    queue = deque([(warehouse.start, initial_automaton, (), (initial_step,))])
    explored = 0
    # Prefix-DFA state keeps full task-relevant history, so this visited set is exact.
    seen = {(warehouse.start, initial_automaton)}
    while queue:
        env_state, automaton_state, actions, trace = queue.popleft()
        explored += 1
        if dfa.is_accepting(automaton_state):
            return ProductWitness("witness", actions, trace, explored)
        if len(trace) >= horizon:
            continue
        if explored >= expansion_budget:
            return ProductWitness("search_budget_exceeded", explored_states=explored)
        for action in ACTIONS[:-1]:
            next_env = warehouse.transition(env_state, action)
            step = warehouse.trace_step(next_env)
            try:
                next_automaton = dfa.transition(automaton_state, step)
            except SynthesisBudgetExceeded:
                return ProductWitness(
                    "synthesis_budget_exceeded", explored_states=explored
                )
            key = next_env, next_automaton
            if key not in seen:
                seen.add(key)
                queue.append(
                    (next_env, next_automaton, (*actions, action), (*trace, step))
                )
    return ProductWitness("no_witness_within_horizon", explored_states=explored)
