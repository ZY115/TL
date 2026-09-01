"""Compile author-facing Macro TL into the canonical Core-TL AST."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import reduce

from ..core_tl.syntax import And, Atom, Eventually, Formula, Or
from . import definitions_v1, definitions_v2
from .syntax import MacroTask

StageExpander = Callable[[object, str], tuple[Formula, ...]]


def _decision_sequence(task: MacroTask) -> Formula:
    tail: Formula = Eventually(Atom(task.end))
    for stage in reversed(task.stages):
        tail = Eventually(
            And(
                Or(Atom(stage.left_event), Atom(stage.right_event)),
                tail,
            )
        )
    return And(Atom(task.start), tail)


def _and_all(conjuncts: Sequence[Formula]) -> Formula:
    return reduce(And, conjuncts)


def expand_macro_tl(task: MacroTask, *, definition_version: int = 1) -> Formula:
    if definition_version == 1:
        expand_stage = definitions_v1.timed_choice_stage
    elif definition_version == 2:
        expand_stage = definitions_v2.timed_choice_stage
    else:
        raise ValueError("definition_version must be 1 or 2")

    conjuncts = [_decision_sequence(task)]
    for stage in task.stages:
        conjuncts.extend(expand_stage(stage, task.end))
    return _and_all(conjuncts)
