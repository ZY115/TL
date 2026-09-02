"""Deterministic 8x8 warehouse transition system."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

ACTIONS = ("UP", "DOWN", "LEFT", "RIGHT", "WAIT", "STOP")
MOVES = {
    "UP": (0, 1),
    "DOWN": (0, -1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
    "WAIT": (0, 0),
}


@dataclass(frozen=True, slots=True)
class EnvironmentState:
    x: int
    y: int
    battery: int = 40
    load: int = 0


@dataclass(frozen=True, slots=True)
class TraceStep:
    propositions: frozenset[str]
    resources: tuple[tuple[str, int], ...]

    def resource(self, name: str) -> int:
        values = dict(self.resources)
        if name not in values:
            raise KeyError(f"Unknown resource: {name}")
        return values[name]

    def to_dict(self) -> dict[str, object]:
        return {
            "propositions": sorted(self.propositions),
            "resources": dict(self.resources),
        }


class Warehouse:
    def __init__(self, source: Mapping[str, object]):
        self.name = str(source["name"])
        self.width = int(source["width"])
        self.height = int(source["height"])
        if (self.width, self.height) != (8, 8):
            raise ValueError("Pilot 1.0 requires an 8x8 grid")
        self.walls = frozenset(self._coordinate(value) for value in source["walls"])
        labels: dict[tuple[int, int], set[str]] = {}
        for label, values in dict(source["labels"]).items():
            for value in values:
                labels.setdefault(self._coordinate(value), set()).add(str(label))
        self.labels = {
            position: frozenset(values) for position, values in labels.items()
        }
        starts = [position for position, values in self.labels.items() if "S" in values]
        if len(starts) != 1:
            raise ValueError("Every map needs exactly one S cell")
        self.start = EnvironmentState(*starts[0])

    @staticmethod
    def _coordinate(value: object) -> tuple[int, int]:
        x, y = value  # type: ignore[misc]
        return int(x), int(y)

    @classmethod
    def load(cls, path: Path) -> "Warehouse":
        # JSON is a strict YAML 1.2 subset; no parser-specific YAML features are used.
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def propositions(self, state: EnvironmentState) -> frozenset[str]:
        labels = set(self.labels.get((state.x, state.y), frozenset()))
        labels.add("SAFE" if "X" not in labels else "HAZARD")
        return frozenset(labels)

    def trace_step(self, state: EnvironmentState) -> TraceStep:
        return TraceStep(
            self.propositions(state),
            (("battery", state.battery), ("load", state.load)),
        )

    def transition(self, state: EnvironmentState, action: str) -> EnvironmentState:
        if action == "STOP":
            return state
        if action not in MOVES:
            raise ValueError(f"Unknown action: {action}")
        dx, dy = MOVES[action]
        candidate = (state.x + dx, state.y + dy)
        if (
            not 0 <= candidate[0] < self.width
            or not 0 <= candidate[1] < self.height
            or candidate in self.walls
        ):
            candidate = (state.x, state.y)
        battery = max(0, state.battery - 1)
        load = state.load
        labels = self.labels.get(candidate, frozenset())
        if "A" in labels:
            load = 1
        if "C" in labels:
            load = 0
        return EnvironmentState(candidate[0], candidate[1], battery, load)

    def execute(
        self, actions: list[str], *, horizon: int = 40
    ) -> tuple[TraceStep, ...]:
        state = self.start
        trace = [self.trace_step(state)]
        for action in actions:
            if action == "STOP" or len(trace) >= horizon:
                break
            state = self.transition(state, action)
            trace.append(self.trace_step(state))
        return tuple(trace)

    def positions_with(self, label: str) -> frozenset[tuple[int, int]]:
        return frozenset(
            position for position, labels in self.labels.items() if label in labels
        )

    def path_exists(
        self,
        start_label: str,
        goal_label: str,
        *,
        forbidden_label: str | None = None,
    ) -> bool:
        starts = self.positions_with(start_label)
        goals = self.positions_with(goal_label)
        forbidden = (
            self.positions_with(forbidden_label) if forbidden_label else frozenset()
        )
        queue = deque(position for position in starts if position not in forbidden)
        seen = set(queue)
        while queue:
            position = queue.popleft()
            if position in goals:
                return True
            for dx, dy in MOVES.values():
                neighbor = position[0] + dx, position[1] + dy
                if (
                    0 <= neighbor[0] < self.width
                    and 0 <= neighbor[1] < self.height
                    and neighbor not in self.walls
                    and neighbor not in forbidden
                    and neighbor not in seen
                ):
                    seen.add(neighbor)
                    queue.append(neighbor)
        return False

    def every_path_uses(self, start: str, goal: str, required: str) -> bool:
        return self.path_exists(start, goal) and not self.path_exists(
            start, goal, forbidden_label=required
        )
