"""Finite warehouse maps and environment feasibility.

A map is an 8×8 grid with walls and single-label region cells. A run starts
on ``start``, takes moves (a move into a wall or off the grid keeps the robot
in place), and ends with STOP. Its trace is the label set of every occupied
cell in order, starting with the start cell, so every environment trace has
length ≥ 1.

Two feasibility procedures are provided, deliberately different in kind:

* ``feasible_by_dfa`` explores the finite product of grid cells and DFA
  states. It is exact and needs no length bound: if no accepting product
  state is reachable, no run of any length satisfies the task.
* ``feasible_by_blackbox`` enumerates move sequences up to a bound and asks
  an opaque acceptor about each. A witness proves feasibility; exhaustion
  proves nothing beyond the bound.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import product
from typing import Callable

from .ltlf_dfa import DFA, Letter, Trace

Cell = tuple[int, int]
MOVES: dict[str, tuple[int, int]] = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
    "WAIT": (0, 0),
}


@dataclass(frozen=True)
class Grid:
    name: str
    width: int
    height: int
    start: Cell
    labels: dict[Cell, str] = field(default_factory=dict)
    walls: frozenset[Cell] = frozenset()

    def letter(self, cell: Cell) -> Letter:
        label = self.labels.get(cell)
        return frozenset({label}) if label else frozenset()

    def move(self, cell: Cell, action: str) -> Cell:
        dx, dy = MOVES[action]
        target = (cell[0] + dx, cell[1] + dy)
        if (
            not 0 <= target[0] < self.width
            or not 0 <= target[1] < self.height
            or target in self.walls
        ):
            return cell
        return target

    def trace_of(self, path: list[Cell]) -> Trace:
        return tuple(self.letter(cell) for cell in path)


def _parse(name: str, rows: list[str]) -> Grid:
    labels: dict[Cell, str] = {}
    walls: set[Cell] = set()
    start: Cell | None = None
    for y, row in enumerate(rows):
        for x, char in enumerate(row.split()):
            if char == "#":
                walls.add((x, y))
            elif char == "S":
                start = (x, y)
            elif char != ".":
                labels[(x, y)] = char
    if start is None:
        raise ValueError("map has no start")
    return Grid(name, len(rows[0].split()), len(rows), start, labels, frozenset(walls))


def base_map() -> Grid:
    """Open floor: every region reachable from every other without X."""
    return _parse(
        "warehouse_base",
        [
            "S . . . . . . .",
            ". . . . . . . .",
            ". . A . . . . .",
            ". . . . . . . .",
            ". . . . B . . .",
            ". . . . . . . .",
            ". . X . . . D .",
            ". . . . . . C .",
        ],
    )


def blocked_map() -> Grid:
    """A wall row whose only gap is the hazard cell X.

    S, A, and B lie above the wall; C and D lie below. Reaching C is
    feasible; reaching C without entering X is not — for structural,
    not logical, reasons.
    """
    return _parse(
        "warehouse_blocked",
        [
            "S . . . . . . .",
            ". . A . . . . .",
            ". . . . B . . .",
            "# # # # X # # #",
            ". . . . . . . .",
            ". . . . . . D .",
            ". . . . . . C .",
            ". . . . . . . .",
        ],
    )


MAPS: dict[str, Callable[[], Grid]] = {"base": base_map, "blocked": blocked_map}


def feasible_by_dfa(grid: Grid, dfa: DFA) -> tuple[bool, list[Cell] | None]:
    """Exact product reachability; returns a shortest feasible path."""
    start_state = dfa.step(dfa.initial, grid.letter(grid.start))
    origin = (grid.start, start_state)
    if start_state in dfa.accepting:
        return True, [grid.start]
    parents: dict[tuple[Cell, int], tuple[tuple[Cell, int], str] | None] = {origin: None}
    queue = deque([origin])
    while queue:
        cell, state = queue.popleft()
        for action in MOVES:
            next_cell = grid.move(cell, action)
            next_state = dfa.step(state, grid.letter(next_cell))
            node = (next_cell, next_state)
            if node in parents:
                continue
            parents[node] = ((cell, state), action)
            if next_state in dfa.accepting:
                path = [next_cell]
                cursor: tuple[Cell, int] | None = (cell, state)
                while cursor is not None:
                    path.append(cursor[0])
                    parent = parents[cursor]
                    cursor = parent[0] if parent else None
                return True, list(reversed(path))
            queue.append(node)
    return False, None


def feasible_by_blackbox(
    grid: Grid, accepts: Callable[[Trace], bool], max_moves: int
) -> tuple[bool | None, list[Cell] | None, int]:
    """Bounded search; ``None`` means no witness within the bound."""
    tried = 0
    for length in range(0, max_moves + 1):
        for actions in product(MOVES, repeat=length):
            path = [grid.start]
            for action in actions:
                path.append(grid.move(path[-1], action))
            tried += 1
            if accepts(grid.trace_of(path)):
                return True, path, tried
    return None, None, tried


def render(grid: Grid, path: list[Cell] | None = None) -> str:
    on_path = set(path or [])
    rows = []
    for y in range(grid.height):
        cells = []
        for x in range(grid.width):
            cell = (x, y)
            if cell in grid.walls:
                cells.append("#")
            elif cell == grid.start:
                cells.append("S")
            elif cell in grid.labels:
                cells.append(grid.labels[cell])
            elif cell in on_path:
                cells.append("*")
            else:
                cells.append(".")
        rows.append(" ".join(cells))
    return "\n".join(rows)
