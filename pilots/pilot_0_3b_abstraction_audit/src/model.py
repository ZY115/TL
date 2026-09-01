"""Task-family model for branch-dependent bounded obligations."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class Stage:
    index: int
    left_event: str
    left_goal: str
    left_bound: int
    right_event: str
    right_goal: str
    right_bound: int

    def fields(self) -> tuple[str, str, int, str, str, int]:
        return (
            self.left_event,
            self.left_goal,
            self.left_bound,
            self.right_event,
            self.right_goal,
            self.right_bound,
        )


ALL_STAGES = tuple(
    Stage(
        index=index,
        left_event=f"L{index}",
        left_goal=f"P{index}",
        left_bound=8,
        right_event=f"R{index}",
        right_goal=f"Q{index}",
        right_bound=10,
    )
    for index in range(1, 7)
)


def stages_for_k(k: int) -> tuple[Stage, ...]:
    if not 0 <= k <= 6:
        raise ValueError("Pilot 0.3 requires 0 <= k <= 6")
    return ALL_STAGES[:k]


def with_left_goal_rewired(
    stages: tuple[Stage, ...], stage_index: int
) -> tuple[Stage, ...]:
    """Replace Pq with Xq for one 1-based stage q."""

    if not 1 <= stage_index <= len(stages):
        raise ValueError("stage_index is outside the active stage set")
    changed = list(stages)
    changed[stage_index - 1] = replace(
        changed[stage_index - 1], left_goal=f"X{stage_index}"
    )
    return tuple(changed)
