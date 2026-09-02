"""P0 dual-reference conformance gate and deterministic trace mixtures."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable, Sequence

from environments.warehouse import MOVES, TraceStep, Warehouse
from neutral_ir.interpreter import evaluate_ir
from neutral_ir.schema import TaskSpec
from reference.automaton import compile_reference_automaton

HORIZON = 40
TRACE_COUNT = 50_000
MIXTURE_COUNTS = {
    "uniform_random": 20_000,
    "constructive_satisfying": 15_000,
    "targeted_mutation": 15_000,
}


def shortest_actions(
    warehouse: Warehouse,
    start: tuple[int, int],
    goal_label: str,
    *,
    forbidden: str | None = "X",
) -> tuple[list[str], tuple[int, int]]:
    goals = warehouse.positions_with(goal_label)
    forbidden_positions = (
        warehouse.positions_with(forbidden) if forbidden else frozenset()
    )
    queue = deque([(start, [])])
    seen = {start}
    for_position = {value: key for key, value in MOVES.items() if key != "WAIT"}
    while queue:
        position, actions = queue.popleft()
        if position in goals:
            return actions, position
        for (dx, dy), action in for_position.items():
            neighbor = position[0] + dx, position[1] + dy
            if (
                0 <= neighbor[0] < warehouse.width
                and 0 <= neighbor[1] < warehouse.height
                and neighbor not in warehouse.walls
                and neighbor not in forbidden_positions
                and neighbor not in seen
            ):
                seen.add(neighbor)
                queue.append((neighbor, [*actions, action]))
    raise AssertionError(f"No canonical path to {goal_label}")


def canonical_satisfying_actions(warehouse: Warehouse) -> list[str]:
    actions: list[str] = []
    position = (warehouse.start.x, warehouse.start.y)
    for label in ("A", "B", "C", "D"):
        segment, position = shortest_actions(warehouse, position, label)
        actions.extend(segment)
    return actions


def _uniform_actions(rng: random.Random) -> list[str]:
    length = rng.randint(0, HORIZON - 1)
    return [rng.choice(("UP", "DOWN", "LEFT", "RIGHT", "WAIT")) for _ in range(length)]


def _constructive_actions(base: Sequence[str], rng: random.Random) -> list[str]:
    actions = list(base)
    # Padding after every required waypoint preserves all training deadlines.
    actions.extend(["WAIT"] * rng.randint(0, 5))
    return actions[: HORIZON - 1]


def _mutated_actions(base: Sequence[str], rng: random.Random) -> list[str]:
    actions = _constructive_actions(base, rng)
    if not actions:
        return ["WAIT"]
    mode = rng.randrange(3)
    index = rng.randrange(len(actions))
    if mode == 0:
        actions[index] = "WAIT"
    elif mode == 1 and len(actions) < HORIZON - 1:
        actions.insert(index, "WAIT")
    else:
        actions.pop(index)
    return actions


def validation_traces(
    warehouse: Warehouse, *, seed: int
) -> Iterable[tuple[str, tuple[TraceStep, ...]]]:
    """Materialize the pre-committed 50k calibration suite for one task seed.

    Both the dual-reference P0 gate and the frozen-arm conformance gate call
    this function. Keeping trace construction in one place makes "the same
    suite" executable rather than merely documentary.
    """

    rng = random.Random(seed)
    canonical = canonical_satisfying_actions(warehouse)
    generators = {
        "uniform_random": lambda: _uniform_actions(rng),
        "constructive_satisfying": lambda: _constructive_actions(canonical, rng),
        "targeted_mutation": lambda: _mutated_actions(canonical, rng),
    }
    for category, count in MIXTURE_COUNTS.items():
        for _ in range(count):
            yield category, warehouse.execute(generators[category](), horizon=HORIZON)


def validation_rows(
    task: TaskSpec, warehouse: Warehouse, *, seed: int
) -> list[dict[str, object]]:
    canonical = canonical_satisfying_actions(warehouse)
    canonical_trace = warehouse.execute(canonical, horizon=HORIZON)
    if not evaluate_ir(task, canonical_trace):
        raise AssertionError(f"Canonical trace does not satisfy {task.id}")
    automaton = compile_reference_automaton(task, horizon=HORIZON)
    counters = {
        category: {"matches": 0, "mismatches": 0, "satisfying": 0}
        for category in MIXTURE_COUNTS
    }
    for category, trace in validation_traces(warehouse, seed=seed):
        direct = evaluate_ir(task, trace)
        reference = automaton.accepts(trace)
        counters[category]["matches"] += int(direct == reference)
        counters[category]["mismatches"] += int(direct != reference)
        counters[category]["satisfying"] += int(direct)
    rows = []
    for category, count in MIXTURE_COUNTS.items():
        values = counters[category]
        rows.append(
            {
                "task_id": task.id,
                "trace_type": category,
                "num_trajectories": count,
                "direct_reference_matches": values["matches"],
                "direct_reference_mismatches": values["mismatches"],
                "satisfying_trajectories": values["satisfying"],
                "random_seed": seed,
            }
        )
    return rows
