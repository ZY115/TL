"""Warehouse DSL: a closed, compositional language for authoring warehouse
trace requirements, plus a deterministic parser/formatter and interpreter.

See ``README.md`` for the grammar and finite-trace semantics of every
construct, and ``training_artifacts/`` for worked examples.
"""

from .core import (
    AllOf,
    AnyOf,
    Avoid,
    AvoidUntil,
    Every,
    Order,
    Requirement,
    Visit,
    Within,
    WarehouseSyntaxError,
    canonicalize,
    evaluate_task,
    parse_task,
)

__all__ = [
    "parse_task",
    "canonicalize",
    "evaluate_task",
    "WarehouseSyntaxError",
    "Requirement",
    "Visit",
    "Avoid",
    "AvoidUntil",
    "Order",
    "Within",
    "Every",
    "AllOf",
    "AnyOf",
]
