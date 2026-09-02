"""Pre-committed deterministic training and compositional held-out split."""

from __future__ import annotations

import json

from neutral_ir.schema import (
    AllOf,
    Alternative,
    Avoid,
    CountAtMost,
    Deadline,
    MaintainUntil,
    On,
    Once,
    OrderedVisit,
    Priority,
    Requirement,
    Since,
    TaskSpec,
    Threshold,
    Visit,
    task_to_dict,
)

SPLIT_SEED = 20_261_001


def training_tasks() -> tuple[TaskSpec, ...]:
    expressions = (
        Visit("A"),
        Avoid("X"),
        OrderedVisit(("A", "B", "C")),
        Deadline("A", 1, 10),
        MaintainUntil("X", "C"),
        On("A", Visit("B")),
        Alternative((Visit("A"), Visit("D"))),
        AllOf((Visit("A"), Avoid("X"))),
        CountAtMost("X", 1),
        On("B", Once("A")),
        On("C", Since("SAFE", "A")),
        Threshold("battery", ">=", 5),
        Priority((Visit("C"), Visit("D"))),
        On("A", Deadline("B", 1, 10)),
        CountAtMost("A", 2),
    )
    return tuple(
        TaskSpec(f"train_{index:02d}", (Requirement(f"r{index}", expr),))
        for index, expr in enumerate(expressions, 1)
    )


def _heldout_library() -> tuple[tuple[str, object], ...]:
    return (
        (
            "on_alternative_deadline_until",
            On(
                "A",
                Alternative((Deadline("B", 1, 4), MaintainUntil("X", "C"))),
            ),
        ),
        (
            "all_count_on_once",
            AllOf((CountAtMost("X", 2), On("B", Once("A")))),
        ),
        (
            "on_all_since_threshold",
            On(
                "C",
                AllOf((Since("SAFE", "A"), Threshold("battery", ">=", 5))),
            ),
        ),
        (
            "priority_nested_alternative",
            Priority(
                (
                    Alternative((Deadline("C", 1, 12), Visit("D"))),
                    OrderedVisit(("A", "B", "C")),
                )
            ),
        ),
        (
            "on_count",
            On("A", CountAtMost("X", 1)),
        ),
        (
            "alternative_threshold_until",
            Alternative(
                (
                    Threshold("battery", ">=", 10),
                    MaintainUntil("X", "D"),
                )
            ),
        ),
        (
            "all_priority_deadline",
            AllOf(
                (
                    Priority((Visit("C"), Visit("D"))),
                    Deadline("A", 1, 8),
                )
            ),
        ),
        (
            "on_alternative_once_since",
            On(
                "C",
                Alternative((Once("B"), Since("SAFE", "A"))),
            ),
        ),
        (
            "count_with_order",
            AllOf((CountAtMost("X", 1), OrderedVisit(("A", "D", "C")))),
        ),
        (
            "deep_scope",
            On(
                "A",
                AllOf(
                    (
                        Alternative((Deadline("B", 1, 6), Visit("D"))),
                        MaintainUntil("X", "C"),
                    )
                ),
            ),
        ),
    )


def heldout_streams() -> tuple[dict[str, object], ...]:
    library = _heldout_library()
    streams = []
    for stream_index in range(20):
        requirements = []
        states = []
        for step in range(10):
            name, expr = library[(stream_index + step) % len(library)]
            requirement = Requirement(
                f"s{stream_index:02d}_r{step + 1:02d}_{name}", expr
            )
            requirements.append(requirement)
            task = TaskSpec(
                f"stream_{stream_index:02d}_T{step + 1:02d}", tuple(requirements)
            )
            states.append(task_to_dict(task))
        streams.append(
            {
                "stream_id": f"stream_{stream_index:02d}",
                "states": states,
            }
        )
    return tuple(streams)


def control_tasks() -> tuple[TaskSpec, ...]:
    return tuple(
        TaskSpec(
            f"control_{index:02d}",
            (
                Requirement(
                    "r1",
                    Deadline(event, 1, bound),
                ),
            ),
        )
        for index, (event, bound) in enumerate(
            (("A", 8), ("B", 9), ("C", 12), ("D", 14)), 1
        )
    )


def canonical_payloads() -> tuple[bytes, bytes, bytes]:
    training = (
        json.dumps(
            [task_to_dict(task) for task in training_tasks()],
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    heldout = (
        json.dumps(list(heldout_streams()), indent=2, sort_keys=True).encode() + b"\n"
    )
    controls = (
        json.dumps(
            [task_to_dict(task) for task in control_tasks()],
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    return training, heldout, controls
