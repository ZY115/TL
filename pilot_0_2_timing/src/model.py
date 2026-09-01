"""Fixed Pilot 0.2 task-family definition."""

from __future__ import annotations

from dataclasses import dataclass, replace

BASE_TARGETS = tuple(f"A{index}" for index in range(1, 11))


@dataclass(frozen=True, slots=True)
class TimingConstraint:
    """One unique-start/unique-end inclusive deadline."""

    name: str
    start: str
    end: str
    bound: int
    lower: int = 1

    def as_tuple(self) -> tuple[str, str, int]:
        return self.start, self.end, self.bound


ALL_CONSTRAINTS = tuple(
    TimingConstraint(
        name=f"C{index}",
        start=f"A{index}",
        end=f"A{index + 5}",
        bound=8,
    )
    for index in range(1, 6)
)


def constraints_for_m(m: int) -> tuple[TimingConstraint, ...]:
    if not 0 <= m <= 5:
        raise ValueError("Pilot 0.2 requires 0 <= m <= 5")
    return ALL_CONSTRAINTS[:m]


def with_changed_bound(
    constraints: tuple[TimingConstraint, ...], constraint_index: int, new_bound: int
) -> tuple[TimingConstraint, ...]:
    """Return a copy with one 1-based constraint bound changed."""

    if not 1 <= constraint_index <= len(constraints):
        raise ValueError("constraint_index is outside the active constraint set")
    changed = list(constraints)
    changed[constraint_index - 1] = replace(
        changed[constraint_index - 1], bound=new_bound
    )
    return tuple(changed)
