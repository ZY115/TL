"""Map geometry and the two feasibility procedures."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import environment as E  # noqa: E402
from src import ltlf_dfa as L  # noqa: E402
from src.blackbox import load_monitor  # noqa: E402


def _dfa(text: str) -> L.DFA:
    return L.build_dfa(L.parse_formula(text))


def test_blocked_map_forces_x_between_b_and_c() -> None:
    grid = E.blocked_map()
    ok, _ = E.feasible_by_dfa(grid, _dfa("F at_C"))
    assert ok
    ok, _ = E.feasible_by_dfa(grid, _dfa("F at_C & G !at_X"))
    assert not ok
    ok, _ = E.feasible_by_dfa(grid, _dfa("F (at_B & X F at_C) & G !at_X"))
    assert not ok


def test_base_map_is_open() -> None:
    grid = E.base_map()
    ok, path = E.feasible_by_dfa(grid, _dfa("F (at_B & X F at_C) & G !at_X"))
    assert ok and path is not None
    assert grid.trace_of(path)[-1] == frozenset({"C"})
    assert all("X" not in step for step in grid.trace_of(path))


def test_product_path_is_shortest_and_valid() -> None:
    grid = E.base_map()
    dfa = _dfa("F at_A")
    ok, path = E.feasible_by_dfa(grid, dfa)
    assert ok and path is not None
    assert dfa.run(grid.trace_of(path))
    # Manhattan distance from S=(0,0) to A=(2,2) is 4 moves: 5 cells.
    assert len(path) == 5


def test_blackbox_search_finds_and_stops_at_bound() -> None:
    grid = E.base_map()
    monitor = load_monitor(
        "class Monitor:\n"
        "    def reset(self):\n        self.seen = False\n"
        "    def step(self, p):\n        self.seen = self.seen or ('A' in p)\n"
        "    def finish(self):\n        return self.seen\n"
    )
    found, path, tried = E.feasible_by_blackbox(grid, monitor, max_moves=4)
    assert found is True and path is not None and len(path) == 5
    found, path, tried = E.feasible_by_blackbox(grid, monitor, max_moves=3)
    assert found is None and path is None
