"""The analysis case pool: released tasks plus coordinator-built variants.

Every case carries the gold IR and one artifact per representation. Where a
blind-authored, oracle-verified artifact exists in the Pilot 1.2 cache it is
used and marked ``authored``; otherwise the coordinator supplies one and it
is marked ``coordinator``. A1 variants are the compiled gold formula — that
*is* the A1 representation of the task. A2 variants are one-line design-C
sources. A3 variants are plain imperative monitors written by hand (see
``artifacts/a3_coordinator``); their ``finish`` bodies are task-specific,
only the trace-collecting preamble is shared.

Experiment B analyses artifacts; it does not measure authoring. Using
coordinator artifacts for the constructed variants is therefore legitimate,
and it is recorded per row.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import paths
from a1_ltlf.language import format_formula
from coordinator_private.build_audit_gold import gold_tasks
from coordinator_private.oracle import schema as ir
from coordinator_private.oracle.ltlf_gold import compile_task

CACHE = paths.PILOT_1_2 / "candidate_cache"
ART = paths.PILOT / "artifacts"

R = ir.Requirement
T = ir.Task


@dataclass(frozen=True)
class Artifact:
    text: str
    source: str  # "authored" | "coordinator" | "gold_compiled"


@dataclass(frozen=True)
class Case:
    case_id: str
    case_class: str
    task: ir.Task
    a1: Artifact
    a2c: Artifact
    a3: Artifact
    map_name: str = "blocked"
    partner: "Case | None" = None  # for version pairs: the "new" task


def _correct_replicates() -> dict[tuple[str, str], list[int]]:
    """Replicates that scored first-attempt correct in Pilot 1.2."""
    import csv

    out: dict[tuple[str, str], list[int]] = {}
    with (paths.PILOT_1_2 / "results/trials.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["first_attempt_correct"] == "True":
                out.setdefault((row["task_id"], row["representation"]), []).append(int(row["replicate"]))
    return {k: sorted(v) for k, v in out.items()}


CORRECT = _correct_replicates()


def _cached(task_id: str, arm: str) -> str:
    """The first blind-authored artifact that Pilot 1.2 verified as correct."""
    replicate = CORRECT[(task_id, arm)][0]
    return (CACHE / f"{task_id}__{arm}__r{replicate:02d}" / "artifact.txt").read_text(
        encoding="utf-8"
    )


def _coordinator_a3(task_id: str) -> Artifact:
    return Artifact((ART / "a3_coordinator" / f"{task_id}.py").read_text(encoding="utf-8"), "coordinator")


def _a1_from_gold(task: ir.Task) -> Artifact:
    return Artifact(format_formula(compile_task(task)), "gold_compiled")


# --------------------------------------------------------------------------
# Released Pilot 1.2 audit tasks. A2c was the rotated design on four of them;
# the others get a coordinator design-C source. audit_10 has no correct A3
# artifact in the cache (0/3), so the coordinator supplies one.
# --------------------------------------------------------------------------

A2C_AUTHORED = {"audit_01", "audit_04", "audit_07", "audit_10"}
A2C_COORDINATOR = {
    "audit_02": "avoid(X)",
    "audit_03": "order(A, B, C)",
    "audit_05": "and(visit(A), every(A, within(B, 1, 2, then=visit(C))))",
    "audit_06": "or(order(A, C), order(D, C))",
    "audit_08": "avoid_until(X, C)",
    "audit_09": "and(visit(A), every(A, within(B, 1, 2, then=avoid_until(X, C))))",
    "audit_11": (
        "and(visit(A), every(A, within(B, 1, 2, then=visit(C))), "
        "every(C, avoid_until(X, D)))"
    ),
    "audit_12": "and(every(A, within(B, 1, 3)), every(B, avoid_until(X, C)))",
}
A3_NO_CORRECT_AUTHORED = {t for t in (x.id for x in gold_tasks()) if (t, "a3") not in CORRECT}


def released_cases() -> list[Case]:
    cases = []
    for task in gold_tasks():
        tid = task.id
        a1 = Artifact(_cached(tid, "a1"), "authored")
        if tid in A2C_AUTHORED:
            a2c = Artifact(_cached(tid, "a2c"), "authored")
        else:
            a2c = Artifact(A2C_COORDINATOR[tid], "coordinator")
        if tid in A3_NO_CORRECT_AUTHORED:
            a3 = _coordinator_a3(tid)
        else:
            a3 = Artifact(_cached(tid, "a3"), "authored")
        cases.append(Case(tid, "released", task, a1, a2c, a3))
    return cases


# --------------------------------------------------------------------------
# Coordinator-built variants. Each is an ordinary warehouse requirement or
# an ordinary mistake in one — a contradictory shift instruction, a rule the
# floor plan cannot satisfy, a redundant clause, a rule whose trigger can
# never fire, a revision of an existing rule.
# --------------------------------------------------------------------------


def _variant(case_id: str, klass: str, a2c: str, *reqs: ir.Expression, map_name="blocked") -> Case:
    task = T(case_id, tuple(R(f"r{i + 1}", e) for i, e in enumerate(reqs)))
    return Case(
        case_id, klass, task, _a1_from_gold(task), Artifact(a2c, "coordinator"),
        _coordinator_a3(case_id), map_name,
    )


def variant_cases() -> list[Case]:
    V, A, O, W, S, Tr, Any_ = (
        ir.Visit, ir.Avoid, ir.Ordered, ir.Within, ir.SafeUntil, ir.Triggered, ir.AnyOf,
    )
    cases = [
        # Logically inconsistent: no trace at all can satisfy them.
        _variant("inc_01", "inconsistent", "and(visit(A), avoid(A))", V("A"), A("A")),
        _variant("inc_02", "inconsistent", "and(order(A, B), avoid(B))", O(("A", "B")), A("B")),
        _variant("inc_03", "inconsistent", "and(visit(A), every(A, within(B, 1, 1)), avoid(B))",
                 V("A"), Tr("A", W("B", 1, 1)), A("B")),
        _variant("inc_04", "inconsistent", "and(avoid_until(X, C), avoid(C))", S("X", "C"), A("C")),
        # Satisfiable in the abstract, infeasible on the blocked floor plan.
        _variant("inf_01", "infeasible", "and(visit(C), avoid(X))", V("C"), A("X")),
        _variant("inf_02", "infeasible", "and(order(B, C), avoid(X))", O(("B", "C")), A("X")),
        _variant("inf_03", "infeasible", "and(visit(A), every(A, within(C, 1, 3)))",
                 V("A"), Tr("A", W("C", 1, 3))),
        _variant("inf_04", "infeasible", "avoid_until(X, C)", S("X", "C")),
        # One requirement is implied by the others.
        _variant("red_01", "redundant", "and(order(A, B, C), order(A, B))", O(("A", "B", "C")), O(("A", "B"))),
        _variant("red_02", "redundant", "and(order(A, B), visit(A))", O(("A", "B")), V("A")),
        _variant("red_03", "redundant", "and(every(A, within(B, 1, 2)), every(A, within(B, 1, 3)))",
                 Tr("A", W("B", 1, 2)), Tr("A", W("B", 1, 3))),
        # A triggered rule whose trigger the other rules forbid.
        _variant("vac_01", "vacuous", "and(avoid(A), every(A, within(B, 1, 2)))", A("A"), Tr("A", W("B", 1, 2))),
        _variant("vac_02", "vacuous", "and(order(C, D), avoid(X), every(X, visit(D)))",
                 O(("C", "D")), A("X"), Tr("X", V("D"))),
    ]
    # Old/new revisions of one rule: numeric, scope, structural, tightening, sideways.
    pairs = [
        ("ver_01", "numeric",
         ("and(visit(A), every(A, within(B, 1, 2)))", (V("A"), Tr("A", W("B", 1, 2)))),
         ("and(visit(A), every(A, within(B, 1, 3)))", (V("A"), Tr("A", W("B", 1, 3))))),
        ("ver_02", "scope",
         ("and(order(A, B, C), avoid(X))", (O(("A", "B", "C")), A("X"))),
         ("and(order(A, B, C), avoid_until(X, C))", (O(("A", "B", "C")), S("X", "C")))),
        ("ver_03", "structural",
         ("order(A, B, C)", (O(("A", "B", "C")),)),
         ("or(order(A, B, C), order(A, D, C))", (Any_((O(("A", "B", "C")), O(("A", "D", "C")))),))),
        ("ver_04", "tightening",
         ("visit(A)", (V("A"),)),
         ("order(A, B)", (O(("A", "B")),))),
        ("ver_05", "sideways",
         ("and(visit(A), avoid(X))", (V("A"), A("X"))),
         ("and(visit(B), avoid(X))", (V("B"), A("X")))),
    ]
    for pid, kind, (old_src, old_reqs), (new_src, new_reqs) in pairs:
        new = _variant(f"{pid}_new", f"version_{kind}", new_src, *new_reqs)
        old = _variant(f"{pid}_old", f"version_{kind}", old_src, *old_reqs)
        cases.append(Case(old.case_id, old.case_class, old.task, old.a1, old.a2c, old.a3, "blocked", new))
    return cases


def all_cases() -> list[Case]:
    return released_cases() + variant_cases()
