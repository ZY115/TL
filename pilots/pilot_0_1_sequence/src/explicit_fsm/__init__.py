"""Canonical explicit-FSM representation."""

from .generator import (
    compile_monitor,
    fsm_modification_metrics,
    fsm_structural_metrics,
    fsm_tree,
    generate_source,
)

__all__ = [
    "compile_monitor",
    "fsm_modification_metrics",
    "fsm_structural_metrics",
    "fsm_tree",
    "generate_source",
]
