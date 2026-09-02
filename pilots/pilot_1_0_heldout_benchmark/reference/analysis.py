"""Bounded language, provenance, and repair analyses over reference artifacts."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from environments.warehouse import TraceStep, Warehouse
from neutral_ir.repair_ops import unit_repairs
from neutral_ir.schema import TaskSpec

from .automaton import DFA, compile_reference_automaton
from .product import ProductWitness, shortest_environment_witness


def language_relation(
    old: DFA, new: DFA, universe: Iterable[tuple[TraceStep, ...]]
) -> tuple[str, tuple[TraceStep, ...] | None]:
    old_only = new_only = None
    for trace in universe:
        before, after = old.accepts(trace), new.accepts(trace)
        if before and not after and old_only is None:
            old_only = trace
        if after and not before and new_only is None:
            new_only = trace
    if old_only is None and new_only is None:
        return "equivalent_on_bounded_universe", None
    if old_only is not None and new_only is None:
        return "new_strictly_stronger_on_bounded_universe", old_only
    if old_only is None and new_only is not None:
        return "new_strictly_weaker_on_bounded_universe", new_only
    return "incomparable_on_bounded_universe", old_only


def minimal_empty_requirement_subset(
    task: TaskSpec,
    warehouse: Warehouse,
    *,
    horizon: int = 40,
) -> tuple[str, ...] | None:
    requirements = task.requirements
    for size in range(1, len(requirements) + 1):
        from itertools import combinations

        for subset in combinations(requirements, size):
            candidate = TaskSpec(f"{task.id}_subset", tuple(subset))
            witness = shortest_environment_witness(
                warehouse,
                compile_reference_automaton(candidate, horizon=horizon),
                horizon=horizon,
            )
            if witness.status == "no_witness_within_horizon":
                return tuple(requirement.id for requirement in subset)
    return None


def fewest_unit_repairs(
    task: TaskSpec,
    warehouse: Warehouse,
    *,
    horizon: int = 40,
    max_depth: int = 4,
) -> tuple[str, tuple[str, ...], TaskSpec | None]:
    queue = deque([(task, ())])
    seen = {repr(task)}
    while queue:
        candidate, edits = queue.popleft()
        witness = shortest_environment_witness(
            warehouse,
            compile_reference_automaton(candidate, horizon=horizon),
            horizon=horizon,
        )
        if witness.status == "witness":
            return "repair_found", edits, candidate
        if len(edits) >= max_depth:
            continue
        for label, repaired in unit_repairs(candidate):
            key = repr(repaired)
            if key not in seen:
                seen.add(key)
                queue.append((repaired, (*edits, label)))
    return "no_repair_within_depth", (), None
