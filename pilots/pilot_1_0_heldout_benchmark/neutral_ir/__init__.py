"""Neutral, representation-independent task semantics."""

from .interpreter import evaluate_ir, requirement_diagnostics
from .schema import *  # noqa: F403

__all__ = ["evaluate_ir", "requirement_diagnostics"]
