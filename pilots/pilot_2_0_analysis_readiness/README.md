# Pilot 2.0 — Analysis Readiness

The advisor's question was: *"Couldn't you just hand-write these task
monitors?"* Yes — every task here is finite-state and every arm wrote it
correctly in Pilot 1.2. Expressiveness cannot separate the representations.
This pilot asks the question that can: **once the artifact exists, what can
be asked of it, and at what cost?**

No authors, no agents, no budget. Thirty cases, eight questions, three
representations, pure code. Runtime for the whole experiment: about a minute.

## Setup

**Representations.** The three arms of Pilot 1.2, analysed as artifacts:

| Arm | Artifact | Semantic object exposed | Analysis route |
|---|---|---|---|
| A1 | standard LTLf formula | the formula; top-level conjuncts = requirements | progression automaton (exact, unbounded) |
| A2c | design-C DSL source | parse tree; top-level `and` = requirements | frozen adapter → LTLf → same automaton (`adapter_exact`) |
| A3 | Python `Monitor` | none — an opaque acceptor | bounded enumeration (traces ≤ 6, paths ≤ 8 moves) |

**Cases (30).** The twelve released Pilot 1.2 audit tasks, using the
blind-authored artifacts that Pilot 1.2 verified as correct, plus eighteen
coordinator-built variants that are ordinary mistakes in ordinary warehouse
rules: four contradictory instruction sets, four rules the blocked floor
plan cannot satisfy, three with a redundant clause, two whose trigger can
never fire, and five old/new revisions (numeric, scope, structural,
tightening, sideways). Coordinator artifacts are marked as such per row and
were verified against gold on the Pilot 1.2 conformance corpus before
analysis (`tests/test_cases.py`).

**Environment.** An 8×8 floor plan with a wall row whose only gap is the
hazard cell X. Reaching C is feasible; reaching C without X is not.

**Questions.**

| | Question | Needs |
|---|---|---|
| B1 | Is the specification consistent? | whole spec |
| B2 | Which requirements are implied by the others? | requirement units |
| B3 | Can each trigger fire on some satisfying trace? | whole spec + one fact |
| B4 | Is the task feasible on this floor plan? | whole spec + map |
| B5 | Which requirements form the minimal conflict? | requirement units |
| B6 | Fewest requirements to remove to become feasible? | requirement units + map |
| B7 | Is the new version stronger, weaker, equivalent, or incomparable? | two whole specs |
| B8 | Shortest trace satisfying each requirement alone? | requirement units |

Gold answers come from the same automaton run on the coordinator formula
with the gold requirement decomposition. Every representation is scored
against them: **correct**, **inconclusive** (a bounded method that could
not decide), **wrong**, or **n/a** (the question cannot be typed against
this artifact).

## Result

| Question | A1 LTLf | A2c DSL (adapter) | A3 Python (bounded) |
|---|---|---|---|
| B1 consistency | **30/30** exact | **30/30** exact | 26 correct · 4 inconclusive |
| B2 redundancy | **30/30** exact | **30/30** exact | n/a — no requirement units |
| B3 trigger vacuity | **12/12** exact | **12/12** exact | 9 correct · 3 inconclusive |
| B4 map feasibility | **30/30** exact | **30/30** exact | 9 correct · 21 inconclusive |
| B5 minimal conflict | **30/30** exact | **30/30** exact | n/a — no requirement units |
| B6 minimal repair | **30/30** exact | **30/30** exact | n/a — no requirement units |
| B7 version relation | **5/5** exact | **5/5** exact | 5/5 correct (bounded) |
| B8 per-requirement witness | **30/30** exact | **30/30** exact | n/a — no requirement units |

Zero wrong answers anywhere. The three columns differ in *what can be
asked* and *what "no" means*, not in accuracy.

**Cost.** All A1 analysis over 30 cases: 1.9 s total; the largest automaton
had 23 states. A3 bounded search: 41 s, dominated by the map search
(up to 1.9 s per case for 488,281 paths).

## What the table says

**1. Every "no" from the black box is inconclusive.** A3 answered B1
correctly on all 26 consistent cases and could not decide any of the 4
inconsistent ones; it found all 3 vacuous triggers "unknown". Enumeration
can only confirm existence. The formula proves non-existence: `inc_01`–`inc_04`
were refuted in a few milliseconds, with the exact conflicting subset.

**2. The floor plan is where the bound bites.** On the blocked map the
shortest feasible run to C is 12 moves; the black box searched to 8. It
confirmed feasibility for the 9 cases whose witness was ≤ 6 moves and
returned "unknown" for the other 21 — 4 of which are feasible, 17 of which
are not, and it cannot tell them apart. The product automaton decided all 30
exactly, no bound, returning a shortest path each time (`audit_03`: 12
moves; `inf_02`: none exists).

**3. Four of eight questions cannot even be asked of the black box.**
B2, B5, B6, B8 name a requirement. A formula has conjuncts; a DSL source has
`and(...)` children; a monitor has a loop. There is nothing to point at. The
formula answered "`red_03`: requirement 0 is implied by requirement 1",
"`inc_03`: requirements {0,1,2} are jointly inconsistent and no proper
subset is", "`inf_01`: remove requirement 0 and the plan becomes feasible".

**4. The DSL matches LTLf everywhere — with an adapter.** Design C exposes
requirement units syntactically and its constructs map onto the gold IR, so
after a 90-line compiler it answers every question exactly. That is the
whole cost: a compiler the language did not ship with, plus the conformance
test that admits it. Designs A and B would each need their own. This is the
same lesson as Pilot 0.3B and 1.2 seen a third time: **the property that
matters is a conjunctive, compilable surface, not "temporal logic" as
such.**

**5. B3 and B7 need no provenance and the black box handles them —
boundedly.** Vacuity is "whole spec ∧ trigger fires", version relation is a
comparison of two acceptors; both are askable of anything that accepts
traces. The black box got every decidable instance right and every
negative instance "unknown".

## The answer to the advisor

Hand-written code can express the task. It cannot be *asked about*. The
conditions for preferring a formal specification are therefore not about
what the task is, but about what will be done with the specification after
it is written:

| Prefer the formal specification when… | Hand-written code is fine when… |
|---|---|
| you must know, before running, whether the rules conflict, which ones, and what to drop (B1, B5, B6) | the rules will only ever be executed, never inspected |
| you must know whether the plan is achievable on a given floor plan, with a proof when it is not (B4) | feasibility will be discovered by trying |
| you will revise the rules and need to know what the revision changed (B7) | there is one version, forever |
| you need to test, reuse, or transfer individual requirements (B2, B8) | the requirements are welded together on purpose |
| the requirement is a temporal property over a finite alphabet | the requirement counts, measures, ranks, or compares runs |

## Limitations

- Bounded search used H = 6 traces and 8 moves. Larger bounds shift the
  A3 column toward "correct" on positive instances and never toward
  "correct" on negative ones; the asymmetry is the point, the numbers are
  not.
- A single DSL design was adapted. The claim "a DSL can match LTLf" rests
  on one design that happened to have a compilable surface.
- Coordinator-built variants are small (one to three requirements). The
  automaton sizes here (≤ 23 states) say nothing about scaling.
- The repair vocabulary is "remove a requirement" only; `inf_04` (a single
  requirement) has no repair under it, correctly reported as none found.
- Nothing here measures authoring. Pilot 1.2 did, on the same tasks.

## Reproduce

```bash
python -m pytest          # 116 tests: automaton ≡ reference evaluator, adapter ≡ interpreter, pool integrity
python run_experiment.py  # results/analysis_readiness.csv, results/summary.csv
```

Reuses Pilot 1.2's gold, oracle, language, frozen design C, and cached
artifacts by import; owns no oracle or task pool of its own.
