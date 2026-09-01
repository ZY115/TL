"""Deterministic exhaustive and mixed randomized trace generation."""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator, Sequence

RANDOM_CATEGORY_COUNTS = {
    "uniform": 4_000,
    "satisfying": 4_000,
    "incomplete": 3_000,
    "early_future": 3_000,
    "repeated": 3_000,
    "irrelevant": 3_000,
}


def exhaustive_traces(targets: Sequence[str]) -> Iterator[tuple[str, ...]]:
    """Enumerate every trace of lengths zero through ``n + 2``."""

    alphabet = ("O", *targets)
    for length in range(len(targets) + 3):
        yield from itertools.product(alphabet, repeat=length)


def _insert_noise(
    rng: random.Random,
    trace: list[str],
    alphabet: Sequence[str],
    maximum_insertions: int,
) -> list[str]:
    for _ in range(rng.randint(0, maximum_insertions)):
        position = rng.randrange(len(trace) + 1)
        trace.insert(position, rng.choice(alphabet))
    return trace


def _uniform_trace(
    rng: random.Random, targets: Sequence[str], _sample_index: int
) -> tuple[str, ...]:
    alphabet = ("O", *targets)
    length = rng.randint(0, 2 * len(targets) + 4)
    return tuple(rng.choice(alphabet) for _ in range(length))


def _satisfying_trace(
    rng: random.Random, targets: Sequence[str], _sample_index: int
) -> tuple[str, ...]:
    alphabet = ("O", *targets)
    trace = _insert_noise(rng, list(targets), alphabet, 2 * len(targets) + 4)
    return tuple(trace)


def _incomplete_trace(
    rng: random.Random, targets: Sequence[str], _sample_index: int
) -> tuple[str, ...]:
    missing = rng.choice(targets)
    alphabet = tuple(event for event in ("O", *targets) if event != missing)
    length = rng.randint(0, 2 * len(targets) + 4)
    return tuple(rng.choice(alphabet) for _ in range(length))


def _early_future_trace(
    rng: random.Random, targets: Sequence[str], sample_index: int
) -> tuple[str, ...]:
    future_index = rng.randrange(1, len(targets))
    future = targets[future_index]
    if sample_index % 2 == 0:
        # Valid: the premature event is ignored; the full sequence appears later.
        trace = [future, "O", *targets]
    else:
        # Invalid: the future target occurs only before its valid predecessor.
        trace = [future, "O", *(t for t in targets if t != future)]
    return tuple(trace)


def _repeated_trace(
    rng: random.Random, targets: Sequence[str], sample_index: int
) -> tuple[str, ...]:
    missing = rng.choice(targets) if sample_index % 2 else None
    trace: list[str] = []
    for target in targets:
        if target == missing:
            continue
        trace.extend([target] * rng.randint(2, 4))
        if rng.random() < 0.5:
            trace.append("O")
    return tuple(trace)


def _irrelevant_trace(
    rng: random.Random, targets: Sequence[str], sample_index: int
) -> tuple[str, ...]:
    missing = rng.choice(targets) if sample_index % 2 else None
    trace: list[str] = ["O"] * rng.randint(1, 4)
    for target in targets:
        if target == missing:
            continue
        trace.extend(["O"] * rng.randint(1, 4))
        trace.append(target)
        trace.extend(["O"] * rng.randint(0, 3))
    return tuple(trace)


_GENERATORS = {
    "uniform": _uniform_trace,
    "satisfying": _satisfying_trace,
    "incomplete": _incomplete_trace,
    "early_future": _early_future_trace,
    "repeated": _repeated_trace,
    "irrelevant": _irrelevant_trace,
}


def randomized_trace_groups(
    targets: Sequence[str], base_seed: int
) -> Iterator[tuple[str, int, list[tuple[str, ...]]]]:
    """Yield six deterministic categories totaling exactly 20,000 traces."""

    if len(targets) < 2:
        raise ValueError("Randomized mixture is defined for n >= 5 in Pilot 0.1")

    for category_index, (category, count) in enumerate(
        RANDOM_CATEGORY_COUNTS.items(), start=1
    ):
        seed = base_seed + category_index
        rng = random.Random(seed)
        generator = _GENERATORS[category]
        traces = [generator(rng, targets, index) for index in range(count)]
        yield category, seed, traces
