"""Warehouse DSL: a closed, finite-trace domain language for authoring
warehouse operating requirements (pickup, inspection, delivery, charging,
hazard avoidance).

Public API:
    parse_task(source: str) -> RequirementNode
    canonicalize(source: str) -> str
    evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool

See README.md for the complete grammar and finite-trace semantics, and
warehouse_dsl/core.py for the implementation. Design seed tag: 22202.
"""

from .core import (
    AllOf,
    AvoidUntil,
    Either,
    Never,
    Order,
    Visit,
    Whenever,
    Within,
    WarehouseDSLError,
    WarehouseDSLSyntaxError,
    WarehouseDSLValidationError,
    canonicalize,
    evaluate_task,
    parse_task,
)

__all__ = [
    "parse_task",
    "canonicalize",
    "evaluate_task",
    "WarehouseDSLError",
    "WarehouseDSLSyntaxError",
    "WarehouseDSLValidationError",
    "Visit",
    "Never",
    "Order",
    "AvoidUntil",
    "Within",
    "Whenever",
    "AllOf",
    "Either",
]
