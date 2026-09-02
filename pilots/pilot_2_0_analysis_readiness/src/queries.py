"""The eight analysis questions, asked of each representation on its own terms.

Every answer is tagged with a support mode:

* ``native_exact``   — answered from the artifact's own semantic object
* ``adapter_exact``  — answered exactly, after a frozen adapter compiled it
* ``bounded_only``   — answered by enumeration up to a stated bound; a found
                       witness is conclusive, exhaustion is not
* ``no_provenance``  — the question names a requirement and the artifact has
                       no requirement-level structure to name

Gold answers come from the same exact machinery run on the coordinator's
gold formula with the gold requirement decomposition.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable

from . import environment as E
from . import ltlf_dfa as L
from .adapters import design_c as adapter
from .blackbox import bounded_relation, find_witness, load_monitor, trace_count
from .cases import Case
from a1_ltlf.language import Atom, Eventually, Formula
from coordinator_private.oracle import schema as ir
from coordinator_private.oracle.ltlf_gold import compile_expression, compile_task

H_ENUM = 6  # trace length bound for black-box enumeration (55,987 traces)
H_PATH = 8  # move bound for black-box environment search (488,281 paths)
REPAIR_DEPTH = 2

QUERIES = ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8")
DESCRIPTIONS = {
    "B1": "consistency: does any finite trace satisfy every requirement?",
    "B2": "redundancy: which requirements are implied by the others?",
    "B3": "trigger vacuity: can each trigger fire on some satisfying trace?",
    "B4": "environment feasibility on the blocked floor plan",
    "B5": "minimal conflict set (inclusion-minimal unsatisfiable subset)",
    "B6": "minimal repair by removing requirements (depth ≤ 2)",
    "B7": "version relation old vs new, with witness",
    "B8": "per-requirement shortest witness (requirement in isolation)",
}


@dataclass
class Answer:
    support_mode: str
    answer: object
    witness: object = None
    work: int = 0
    bound: str = ""
    provenance_units: int | None = None
    note: str = ""
    runtime_ms: float = 0.0


@dataclass
class Handle:
    """One representation of one task, with whatever structure it exposes."""

    representation: str
    mode: str  # native_exact | adapter_exact | bounded_only
    formula: Formula | None = None
    units: list[Formula] = field(default_factory=list)
    accepts: Callable | None = None
    states: int = 0


def _sorted_units(units: list[Formula]) -> list[Formula]:
    """Canonical unit order, so per-unit answers align across representations."""
    return sorted((L.normalize(u) for u in units), key=L.key)


def handle(case: Case, representation: str) -> Handle:
    if representation == "a1":
        f = L.parse_formula(case.a1.text)
        return Handle("a1", "native_exact", f, _sorted_units(L.conjuncts(f)))
    if representation == "a2c":
        f = adapter.to_ltlf(case.a2c.text)
        return Handle("a2c", "adapter_exact", f, _sorted_units(adapter.requirement_formulas(case.a2c.text)))
    if representation == "a3":
        return Handle("a3", "bounded_only", accepts=load_monitor(case.a3.text))
    if representation == "gold":
        f = compile_task(case.task)
        return Handle("gold", "native_exact", f, _sorted_units([compile_expression(r.expression) for r in case.task.requirements]))
    raise ValueError(representation)


def _timed(fn):
    start = time.perf_counter()
    out = fn()
    out.runtime_ms = round((time.perf_counter() - start) * 1000, 2)
    return out


def _triggers(task: ir.Task) -> list[tuple[str, str]]:
    out = []

    def walk(e, rid):
        if isinstance(e, ir.Triggered):
            out.append((rid, e.trigger))
            walk(e.obligation, rid)
        elif isinstance(e, ir.WithinThen):
            walk(e.then, rid)
        elif isinstance(e, (ir.AnyOf,)):
            for c in e.options:
                walk(c, rid)
        elif isinstance(e, (ir.AllOf,)):
            for c in e.requirements:
                walk(c, rid)

    for r in task.requirements:
        walk(r.expression, r.id)
    return out


# --------------------------------------------------------------------------
# B1 consistency
# --------------------------------------------------------------------------


def b1(h: Handle) -> Answer:
    def exact():
        dfa = L.build_dfa(h.formula)
        w = dfa.shortest_accepted()
        return Answer(h.mode, w is not None, L.trace_text(w), len(dfa.states), "unbounded")

    def bounded():
        w, tried = find_witness(h.accepts, H_ENUM)
        return Answer("bounded_only", True if w is not None else None, L.trace_text(w), tried, f"len<={H_ENUM}")

    return _timed(exact if h.formula is not None else bounded)


# --------------------------------------------------------------------------
# B2 redundancy — needs requirement units
# --------------------------------------------------------------------------


def b2(h: Handle) -> Answer:
    if h.formula is None:
        return Answer("no_provenance", None, note="artifact exposes no requirement units")

    def exact():
        redundant = []
        work = 0
        if len(h.units) > 1:
            for i, unit in enumerate(h.units):
                others = L.conj(*[u for j, u in enumerate(h.units) if j != i])
                ok, _ = L.includes(others, unit)
                work += 1
                if ok:
                    redundant.append(i)
        return Answer(h.mode, tuple(redundant), None, work, "unbounded", len(h.units))

    return _timed(exact)


# --------------------------------------------------------------------------
# B3 trigger vacuity — whole spec ∧ "trigger fires"; no provenance needed
# --------------------------------------------------------------------------


def b3(h: Handle, task: ir.Task) -> Answer:
    triggers = _triggers(task)
    if not triggers:
        return Answer("not_applicable", (), note="task has no triggered rule")

    def exact():
        result = {}
        work = 0
        for rid, t in triggers:
            sat, w = L.satisfiable(L.conj(h.formula, Eventually(Atom(f"at_{t}"))))
            work += 1
            result[f"{rid}:{t}"] = "fires" if sat else "vacuous"
        return Answer(h.mode, tuple(sorted(result.items())), None, work, "unbounded")

    def bounded():
        result = {}
        tried_total = 0
        for rid, t in triggers:
            def fires(trace, t=t):
                return any(t in s for s in trace) and h.accepts(trace)
            w, tried = find_witness(fires, H_ENUM)
            tried_total += tried
            result[f"{rid}:{t}"] = "fires" if w is not None else "unknown"
        return Answer("bounded_only", tuple(sorted(result.items())), None, tried_total, f"len<={H_ENUM}")

    return _timed(exact if h.formula is not None else bounded)


# --------------------------------------------------------------------------
# B4 environment feasibility
# --------------------------------------------------------------------------


def b4(h: Handle, grid: E.Grid) -> Answer:
    def exact():
        dfa = L.build_dfa(h.formula)
        ok, path = E.feasible_by_dfa(grid, dfa)
        return Answer(h.mode, ok, (len(path) - 1) if path else None, len(dfa.states) * 64, "unbounded")

    def bounded():
        found, path, tried = E.feasible_by_blackbox(grid, h.accepts, H_PATH)
        return Answer("bounded_only", found, (len(path) - 1) if path else None, tried, f"moves<={H_PATH}")

    return _timed(exact if h.formula is not None else bounded)


# --------------------------------------------------------------------------
# B5 minimal conflict set — needs units; only meaningful when B1 is false
# --------------------------------------------------------------------------


def b5(h: Handle) -> Answer:
    if h.formula is None:
        return Answer("no_provenance", None, note="artifact exposes no requirement units")

    def exact():
        sat, _ = L.satisfiable(L.conj(*h.units))
        if sat:
            return Answer(h.mode, (), note="consistent; no conflict", provenance_units=len(h.units))
        # deletion-based: drop units while the remainder stays unsatisfiable
        core = list(range(len(h.units)))
        work = 1
        for i in list(core):
            trial = [j for j in core if j != i]
            if not trial:
                continue
            sat, _ = L.satisfiable(L.conj(*[h.units[j] for j in trial]))
            work += 1
            if not sat:
                core = trial
        return Answer(h.mode, tuple(core), None, work, "unbounded", len(h.units))

    return _timed(exact)


# --------------------------------------------------------------------------
# B6 minimal removal repair on the blocked map — needs units
# --------------------------------------------------------------------------


def b6(h: Handle, grid: E.Grid) -> Answer:
    if h.formula is None:
        return Answer("no_provenance", None, note="artifact exposes no requirement units")

    def exact():
        dfa = L.build_dfa(h.formula)
        ok, _ = E.feasible_by_dfa(grid, dfa)
        work = 1
        if ok:
            return Answer(h.mode, (), note="already feasible", provenance_units=len(h.units))
        idx = list(range(len(h.units)))
        for depth in range(1, REPAIR_DEPTH + 1):
            for removed in combinations(idx, depth):
                keep = [h.units[j] for j in idx if j not in removed]
                if not keep:
                    continue
                ok, _ = E.feasible_by_dfa(grid, L.build_dfa(L.conj(*keep)))
                work += 1
                if ok:
                    return Answer(h.mode, removed, None, work, f"depth<={REPAIR_DEPTH}", len(h.units))
        return Answer(h.mode, None, None, work, f"depth<={REPAIR_DEPTH}", len(h.units), "no repair within depth")

    return _timed(exact)


# --------------------------------------------------------------------------
# B7 version relation
# --------------------------------------------------------------------------


def b7(old: Handle, new: Handle) -> Answer:
    def exact():
        rel, w = L.relation(old.formula, new.formula)
        return Answer(old.mode, rel, L.trace_text(w), 2, "unbounded")

    def bounded():
        rel, w, tried = bounded_relation(old.accepts, new.accepts, H_ENUM)
        return Answer("bounded_only", rel, L.trace_text(w), tried, f"len<={H_ENUM}")

    return _timed(exact if old.formula is not None else bounded)


# --------------------------------------------------------------------------
# B8 per-requirement witness — needs units
# --------------------------------------------------------------------------


def b8(h: Handle) -> Answer:
    if h.formula is None:
        return Answer("no_provenance", None, note="artifact exposes no requirement units")

    def exact():
        lengths = []
        work = 0
        for unit in h.units:
            w = L.build_dfa(unit).shortest_accepted()
            work += 1
            lengths.append(len(w) if w is not None else None)
        return Answer(h.mode, tuple(lengths), None, work, "unbounded", len(h.units))

    return _timed(exact)


def gold_units(case: Case) -> int:
    return len(case.task.requirements)


def enumeration_budget() -> dict[str, int]:
    return {"traces_len_le_H_ENUM": trace_count(H_ENUM), "paths_moves_le_H_PATH": sum(5**k for k in range(H_PATH + 1))}
