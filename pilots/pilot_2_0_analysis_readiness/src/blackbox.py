"""Bounded analysis of opaque acceptors, and safe loading of Pilot 1.2 artifacts.

An A3 monitor is a program; an A2 source is interpreted by its own frozen
package. Neither exposes an automaton, so the only representation-agnostic
analysis is to enumerate traces up to a bound and ask. Enumeration is sound
for existence claims (a found witness is real) and silent otherwise: no
witness within the bound is *not* evidence of emptiness. Every result from
this module therefore carries its bound.

Monitors are executed in-process under the same AST validation and builtin
allow-list as Pilot 1.2's subprocess worker. They are our own cached
artifacts, already run once in that sandbox.
"""

from __future__ import annotations

import ast
from itertools import product
from typing import Callable

from . import paths
from .ltlf_dfa import SINGLE_LETTERS, Trace
from coordinator_private.a3_worker import safe_builtins, validate
from coordinator_private.validate_a2_training import _load_design

PILOT_1_2 = paths.PILOT_1_2  # artifacts and oracle are reused from there
Acceptor = Callable[[Trace], bool]

ENUM_ALPHABET = SINGLE_LETTERS  # empty step or one label: 6 letters


def enumerate_traces(max_len: int, alphabet=ENUM_ALPHABET):
    """Every trace of length 0..max_len over the enumeration alphabet."""
    for length in range(0, max_len + 1):
        for letters in product(alphabet, repeat=length):
            yield tuple(letters)


def trace_count(max_len: int, alphabet=ENUM_ALPHABET) -> int:
    n = len(alphabet)
    return sum(n**k for k in range(0, max_len + 1))


def load_monitor(source: str) -> Acceptor:
    tree = ast.parse(source)
    validate(tree)
    namespace: dict[str, object] = {
        "__builtins__": safe_builtins(),
        "__name__": "candidate_monitor",
    }
    exec(compile(tree, "<monitor>", "exec"), namespace, namespace)
    cls = namespace.get("Monitor")
    if not isinstance(cls, type):
        raise ValueError("artifact does not define class Monitor")

    def accepts(trace: Trace) -> bool:
        monitor = cls()
        monitor.reset()
        for step in trace:
            monitor.step(set(step))
        result = monitor.finish()
        if not isinstance(result, bool):
            raise TypeError("Monitor.finish() must return bool")
        return result

    return accepts


_DESIGN_C = None


def design_c():
    global _DESIGN_C
    if _DESIGN_C is None:
        _DESIGN_C = _load_design("design_c")
    return _DESIGN_C


def load_dsl_c(source: str) -> Acceptor:
    module = design_c()
    module.parse_task(source)
    return lambda trace: bool(module.evaluate_task(source, trace))


def find_witness(accepts: Acceptor, max_len: int) -> tuple[Trace | None, int]:
    tried = 0
    for trace in enumerate_traces(max_len):
        tried += 1
        if accepts(trace):
            return trace, tried
    return None, tried


def bounded_relation(
    old: Acceptor, new: Acceptor, max_len: int
) -> tuple[str, Trace | None, int]:
    """Compare two acceptors on every enumerated trace up to the bound."""
    old_only: Trace | None = None
    new_only: Trace | None = None
    tried = 0
    for trace in enumerate_traces(max_len):
        tried += 1
        a, b = old(trace), new(trace)
        if a and not b and old_only is None:
            old_only = trace
        if b and not a and new_only is None:
            new_only = trace
        if old_only is not None and new_only is not None:
            break
    if old_only is None and new_only is None:
        return "equivalent_up_to_bound", None, tried
    if new_only is None:
        return "strictly_stronger_up_to_bound", old_only, tried
    if old_only is None:
        return "strictly_weaker_up_to_bound", new_only, tried
    return "incomparable", old_only, tried
