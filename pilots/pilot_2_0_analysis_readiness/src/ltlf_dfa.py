"""Exact finite-trace analysis of standard LTLf by formula progression.

A formula is turned into a deterministic automaton whose states are
normalized residual formulas (Bacchus–Kabanza progression). Reading a letter
σ from state φ moves to ``prog(φ, σ)``; a state accepts iff its residual is
satisfied by the empty suffix. Because the residuals are drawn from a finite
closure, the automaton is finite, and every language question below —
emptiness, inclusion, equivalence, shortest witness — is answered exactly
and without any trace-length bound.

Strong next is handled with an explicit ``NONEMPTY`` residual (``F true``):
``prog(X φ, σ) = φ ∧ NONEMPTY``, so a trace that ends right after σ cannot
satisfy ``X φ`` however trivial φ is. This matches the evaluator in
``a1_ltlf.language`` exactly; ``tests/test_dfa.py`` checks that on tens of
thousands of traces.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from . import paths  # noqa: F401  (sys.path side effect)
from a1_ltlf.language import (
    Always,
    And,
    Atom,
    Eventually,
    Formula,
    Implies,
    Next,
    Not,
    Or,
    Until,
    evaluate,
    format_formula,
    parse_formula,
)

Letter = frozenset[str]
Trace = tuple[Letter, ...]


# --------------------------------------------------------------------------
# Internal constants and n-ary connectives (never exposed to authors).
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrueF(Formula):
    pass


@dataclass(frozen=True, slots=True)
class FalseF(Formula):
    pass


@dataclass(frozen=True, slots=True)
class NAnd(Formula):
    items: tuple[Formula, ...]


@dataclass(frozen=True, slots=True)
class NOr(Formula):
    items: tuple[Formula, ...]


TRUE = TrueF()
FALSE = FalseF()
NONEMPTY = Eventually(TRUE)

ALPHABET: tuple[Letter, ...] = tuple(
    frozenset(combo)
    for size in range(len(paths.LABELS) + 1)
    for combo in combinations(paths.LABELS, size)
)
SINGLE_LETTERS: tuple[Letter, ...] = (frozenset(),) + tuple(
    frozenset({label}) for label in paths.LABELS
)


# --------------------------------------------------------------------------
# Canonical form.
# --------------------------------------------------------------------------


def key(f: Formula) -> str:
    if isinstance(f, TrueF):
        return "T"
    if isinstance(f, FalseF):
        return "F"
    if isinstance(f, Atom):
        return f"a:{f.name}"
    if isinstance(f, Not):
        return f"!({key(f.operand)})"
    if isinstance(f, NAnd):
        return "&(" + ",".join(key(i) for i in f.items) + ")"
    if isinstance(f, NOr):
        return "|(" + ",".join(key(i) for i in f.items) + ")"
    if isinstance(f, Next):
        return f"X({key(f.operand)})"
    if isinstance(f, Eventually):
        return f"E({key(f.operand)})"
    if isinstance(f, Always):
        return f"G({key(f.operand)})"
    if isinstance(f, Until):
        return f"U({key(f.left)},{key(f.right)})"
    raise TypeError(type(f))


def _nary(cls, items: Iterable[Formula], absorb: Formula, unit: Formula) -> Formula:
    flat: dict[str, Formula] = {}
    for item in items:
        if isinstance(item, cls):
            for inner in item.items:
                flat[key(inner)] = inner
        else:
            flat[key(item)] = item
    if key(absorb) in flat:
        return absorb
    flat.pop(key(unit), None)
    if not flat:
        return unit
    if len(flat) == 1:
        return next(iter(flat.values()))
    return cls(tuple(flat[k] for k in sorted(flat)))


def _negate(f: Formula) -> Formula:
    if isinstance(f, TrueF):
        return FALSE
    if isinstance(f, FalseF):
        return TRUE
    if isinstance(f, Not):
        return f.operand
    if isinstance(f, NAnd):
        return _nary(NOr, (_negate(i) for i in f.items), TRUE, FALSE)
    if isinstance(f, NOr):
        return _nary(NAnd, (_negate(i) for i in f.items), FALSE, TRUE)
    if isinstance(f, Eventually):
        return Always(_negate(f.operand))
    if isinstance(f, Always):
        return Eventually(_negate(f.operand))
    return Not(f)


def normalize(f: Formula) -> Formula:
    if isinstance(f, (TrueF, FalseF, Atom)):
        return f
    if isinstance(f, Not):
        return _negate(normalize(f.operand))
    if isinstance(f, And):
        return _nary(NAnd, (normalize(f.left), normalize(f.right)), FALSE, TRUE)
    if isinstance(f, Or):
        return _nary(NOr, (normalize(f.left), normalize(f.right)), TRUE, FALSE)
    if isinstance(f, NAnd):
        return _nary(NAnd, (normalize(i) for i in f.items), FALSE, TRUE)
    if isinstance(f, NOr):
        return _nary(NOr, (normalize(i) for i in f.items), TRUE, FALSE)
    if isinstance(f, Implies):
        return _nary(NOr, (_negate(normalize(f.left)), normalize(f.right)), TRUE, FALSE)
    if isinstance(f, Next):
        inner = normalize(f.operand)
        return FALSE if isinstance(inner, FalseF) else Next(inner)
    if isinstance(f, Eventually):
        inner = normalize(f.operand)
        if isinstance(inner, FalseF):
            return FALSE
        if isinstance(inner, Eventually):
            return inner
        return Eventually(inner)
    if isinstance(f, Always):
        inner = normalize(f.operand)
        if isinstance(inner, TrueF):
            return TRUE
        if isinstance(inner, FalseF):
            return FALSE
        if isinstance(inner, Always):
            return inner
        return Always(inner)
    if isinstance(f, Until):
        left, right = normalize(f.left), normalize(f.right)
        if isinstance(right, FalseF):
            return FALSE
        if isinstance(right, TrueF):
            return NONEMPTY
        if isinstance(left, FalseF):
            return right
        if isinstance(left, TrueF):
            return Eventually(right)
        return Until(left, right)
    raise TypeError(type(f))


# --------------------------------------------------------------------------
# Progression and empty-suffix evaluation.
# --------------------------------------------------------------------------


def progress(f: Formula, letter: Letter) -> Formula:
    """Residual that the suffix after ``letter`` must satisfy."""
    if isinstance(f, (TrueF, FalseF)):
        return f
    if isinstance(f, Atom):
        name = f.name[3:] if f.name.startswith("at_") else f.name
        return TRUE if name in letter else FALSE
    if isinstance(f, Not):
        return _negate(progress(f.operand, letter))
    if isinstance(f, NAnd):
        return _nary(NAnd, (progress(i, letter) for i in f.items), FALSE, TRUE)
    if isinstance(f, NOr):
        return _nary(NOr, (progress(i, letter) for i in f.items), TRUE, FALSE)
    if isinstance(f, Next):
        return _nary(NAnd, (f.operand, NONEMPTY), FALSE, TRUE)
    if isinstance(f, Eventually):
        return _nary(NOr, (progress(f.operand, letter), f), TRUE, FALSE)
    if isinstance(f, Always):
        return _nary(NAnd, (progress(f.operand, letter), f), FALSE, TRUE)
    if isinstance(f, Until):
        hold = _nary(NAnd, (progress(f.left, letter), f), FALSE, TRUE)
        return _nary(NOr, (progress(f.right, letter), hold), TRUE, FALSE)
    raise TypeError(type(f))


def empty_accepts(f: Formula) -> bool:
    if isinstance(f, TrueF):
        return True
    if isinstance(f, (FalseF, Atom, Next, Eventually, Until)):
        return False
    if isinstance(f, Not):
        return not empty_accepts(f.operand)
    if isinstance(f, NAnd):
        return all(empty_accepts(i) for i in f.items)
    if isinstance(f, NOr):
        return any(empty_accepts(i) for i in f.items)
    if isinstance(f, Always):
        return True
    raise TypeError(type(f))


def evaluate_by_progression(f: Formula, trace: Trace) -> bool:
    residual = normalize(f)
    for letter in trace:
        residual = progress(residual, letter)
    return empty_accepts(residual)


# --------------------------------------------------------------------------
# The automaton.
# --------------------------------------------------------------------------


class StateBudgetExceeded(RuntimeError):
    pass


@dataclass
class DFA:
    formula: Formula
    states: list[Formula]
    index: dict[str, int]
    accepting: set[int]
    delta: dict[tuple[int, Letter], int]
    alphabet: tuple[Letter, ...]

    @property
    def initial(self) -> int:
        return 0

    def step(self, state: int, letter: Letter) -> int:
        return self.delta[state, letter]

    def run(self, trace: Trace) -> bool:
        state = 0
        for letter in trace:
            state = self.delta[state, letter]
        return state in self.accepting

    def shortest_accepted(self) -> Trace | None:
        """BFS over letters; the empty trace is a candidate of length zero."""
        if 0 in self.accepting:
            return ()
        seen = {0}
        queue: deque[tuple[int, tuple[Letter, ...]]] = deque([(0, ())])
        while queue:
            state, prefix = queue.popleft()
            for letter in self.alphabet:
                target = self.delta[state, letter]
                if target in seen:
                    continue
                path = prefix + (letter,)
                if target in self.accepting:
                    return path
                seen.add(target)
                queue.append((target, path))
        return None

    def is_empty(self) -> bool:
        return self.shortest_accepted() is None


def build_dfa(
    f: Formula, *, alphabet: tuple[Letter, ...] = ALPHABET, max_states: int = 50_000
) -> DFA:
    root = normalize(f)
    states = [root]
    index = {key(root): 0}
    delta: dict[tuple[int, Letter], int] = {}
    queue = deque([0])
    while queue:
        current = queue.popleft()
        for letter in alphabet:
            residual = progress(states[current], letter)
            k = key(residual)
            target = index.get(k)
            if target is None:
                if len(states) >= max_states:
                    raise StateBudgetExceeded(f"more than {max_states} residual states")
                target = len(states)
                states.append(residual)
                index[k] = target
                queue.append(target)
            delta[current, letter] = target
    accepting = {i for i, state in enumerate(states) if empty_accepts(state)}
    return DFA(root, states, index, accepting, delta, alphabet)


# --------------------------------------------------------------------------
# Language questions, phrased on formulas.
# --------------------------------------------------------------------------


def conj(*items: Formula) -> Formula:
    return _nary(NAnd, (normalize(i) for i in items), FALSE, TRUE)


def neg(f: Formula) -> Formula:
    return _negate(normalize(f))


def satisfiable(f: Formula, **kw) -> tuple[bool, Trace | None]:
    witness = build_dfa(f, **kw).shortest_accepted()
    return witness is not None, witness


def includes(f: Formula, g: Formula, **kw) -> tuple[bool, Trace | None]:
    """L(f) ⊆ L(g); on failure the witness is in L(f) \\ L(g)."""
    sat, witness = satisfiable(conj(f, neg(g)), **kw)
    return not sat, witness


def relation(old: Formula, new: Formula, **kw) -> tuple[str, Trace | None]:
    new_in_old, w1 = includes(new, old, **kw)
    old_in_new, w2 = includes(old, new, **kw)
    if new_in_old and old_in_new:
        return "equivalent", None
    if new_in_old:
        return "strictly_stronger", w2  # old accepts w2, new rejects it
    if old_in_new:
        return "strictly_weaker", w1  # new accepts w1, old rejects it
    return "incomparable", w1 or w2


def conjuncts(f: Formula) -> list[Formula]:
    """Top-level requirement units of an authored formula."""
    root = normalize(f)
    if isinstance(root, NAnd):
        return list(root.items)
    return [root]


def to_text(f: Formula) -> str:
    """Readable rendering of an internal formula (for reports only)."""
    if isinstance(f, TrueF):
        return "true"
    if isinstance(f, FalseF):
        return "false"
    if isinstance(f, NAnd):
        return "(" + " & ".join(to_text(i) for i in f.items) + ")"
    if isinstance(f, NOr):
        return "(" + " | ".join(to_text(i) for i in f.items) + ")"
    if isinstance(f, Not):
        return f"!{to_text(f.operand)}"
    if isinstance(f, Next):
        return f"X {to_text(f.operand)}"
    if isinstance(f, Eventually):
        return f"F {to_text(f.operand)}"
    if isinstance(f, Always):
        return f"G {to_text(f.operand)}"
    if isinstance(f, Until):
        return f"({to_text(f.left)} U {to_text(f.right)})"
    return format_formula(f)


def trace_text(trace: Trace | None) -> str:
    if trace is None:
        return "-"
    return "[" + ", ".join("+".join(sorted(step)) or "O" for step in trace) + "]"


__all__ = [
    "ALPHABET",
    "SINGLE_LETTERS",
    "DFA",
    "StateBudgetExceeded",
    "build_dfa",
    "conj",
    "conjuncts",
    "evaluate",
    "evaluate_by_progression",
    "includes",
    "neg",
    "normalize",
    "parse_formula",
    "relation",
    "satisfiable",
    "to_text",
    "trace_text",
]
