"""Independent mathematical oracle for ordered-subsequence semantics."""

from __future__ import annotations

from collections.abc import Sequence


def sequence_oracle(trajectory: Sequence[str], targets: Sequence[str]) -> bool:
    """Return True iff ``targets`` occurs as an ordered subsequence.

    This implementation is intentionally independent of all three benchmark
    representations.  It directly implements the increasing-index definition.
    """

    target_index = 0
    for event in trajectory:
        if target_index < len(targets) and event == targets[target_index]:
            target_index += 1
    return target_index == len(targets)
