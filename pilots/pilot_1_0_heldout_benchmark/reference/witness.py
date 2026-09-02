"""Witness serialization helpers."""

from __future__ import annotations

from .product import ProductWitness


def witness_to_dict(witness: ProductWitness) -> dict[str, object]:
    return {
        "status": witness.status,
        "actions": list(witness.actions),
        "trace": [step.to_dict() for step in witness.trace],
        "explored_states": witness.explored_states,
    }
