"""Warehouse DSL: a small closed language for authoring warehouse tasks.

Public API:

    parse_task(source: str) -> Requirement
    canonicalize(source: str) -> str
    evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool

See ``README.md`` (next to this package) for the full grammar and the
finite-trace semantics of every construct.
"""

from .core import (
    And,
    AnyOf,
    AvoidUntil,
    Avoid,
    Every,
    Label,
    Or,
    Order,
    Visit,
    Within,
    WarehouseDSLError,
    WarehouseSyntaxError,
    WarehouseValidationError,
    canonicalize,
    evaluate_task,
    parse_task,
)

__all__ = [
    "parse_task",
    "canonicalize",
    "evaluate_task",
    "WarehouseDSLError",
    "WarehouseSyntaxError",
    "WarehouseValidationError",
    "Label",
    "AnyOf",
    "Visit",
    "Avoid",
    "Order",
    "Within",
    "AvoidUntil",
    "Every",
    "And",
    "Or",
]
