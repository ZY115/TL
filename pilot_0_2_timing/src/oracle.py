"""Independent oracle for unique-event ordered sequences with deadlines."""

from __future__ import annotations

from collections.abc import Sequence

from .model import TimingConstraint


def timed_sequence_oracle(
    trajectory: Sequence[str],
    targets: Sequence[str],
    timing_constraints: Sequence[TimingConstraint],
) -> bool:
    """Evaluate the mathematical Pilot 0.2 definition directly."""

    target_set = set(targets)
    observed_targets = [event for event in trajectory if event in target_set]
    if len(observed_targets) != len(set(observed_targets)):
        return False
    if observed_targets != list(targets):
        return False

    positions = {
        event: step for step, event in enumerate(trajectory) if event in target_set
    }
    for constraint in timing_constraints:
        if positions[constraint.end] - positions[constraint.start] > constraint.bound:
            return False
    return True
