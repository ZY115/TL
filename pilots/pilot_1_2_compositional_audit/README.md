# Pilot 1.2 — Compositional Blind Discrimination Audit

Pilot 1.2 re-runs the Pilot 1.1 apparatus after fixing the three defects that
iteration exposed, with a capable memoryless author instead of a 3B local
model. Its primary outcome is **first-attempt hidden-suite correctness** when
standard LTLf, three independently designed task DSLs, and handwritten Python
are all authored blind from the same natural-language task card.

It does not study source size, infrastructure evolution, analysis readiness,
human maintainability, or RL. It does not assume that LTLf wins.

## Status — iteration 1 complete, gate passed

| Stage | Status |
|---|---|
| Preserve Pilot 1.1 | complete; tree hash frozen and re-verified after the run |
| Compositional gold IR (`WithinThen`) | complete; 16 training + 12 audit tasks, zero LTLf mismatches |
| A1 reference without the `X^l` trap | complete |
| Symmetric worked examples (16 per arm, oracle-verified) | complete |
| Three blind A2 designs (Sonnet) | complete; frozen; 927,888 conformance evaluations, zero mismatches |
| Realistic task pool (Haiku curator, realism rule) | complete; 18 cards, 12 selected, no replacement needed |
| Ambiguity audit | complete; 4 cards repaired toward curator intent, 1 contract-confirmed |
| Stage 1 — 12 tasks × 3 arms × 1 replicate | complete; 36 trials |
| Stage 2 — +2 replicates on the 4 non-unanimous tasks | complete; 24 trials |
| Hidden evaluation and gate | complete; 60 trials |

**Gate verdict: `passes_gate = true` on the descriptive-spread criterion.**
Four of twelve tasks separate the arm classes by ≥ 20 points; no ceiling
failure (8/12 < 80 %); no floor failure. **The paired McNemar test is not
significant** — with twelve tasks and majority-vote outcomes there is one
discordant task per arm pair, far below the six needed for p < 0.05. The
apparatus produces real signal; the *statistical* claim at this size is weak
and must be reported as such.

## Headline result

| Arm | Trials | Parse | First-attempt correct | False-accept rate | False-reject rate |
|---|---:|---:|---:|---:|---:|
| A1 standard LTLf | 20 | 100 % | **20 / 20** | 0.000 | 0.000 |
| A2a (design A) | 6 | 100 % | 4 / 6 | 0.092 | 0.000 |
| A2b (design B) | 8 | 100 % | 7 / 8 | 0.036 | 0.000 |
| A2c (design C) | 6 | 100 % | 6 / 6 | 0.000 | 0.000 |
| A2 pooled (rotated) | 20 | 100 % | **17 / 20** | 0.042 | 0.000 |
| A3 handwritten Python | 20 | 100 % | **16 / 20** | 0.006 | 0.011 |

Every one of the 60 artifacts parsed and ran. Nothing was `UNSUPPORTED`. All
seven failures are semantic.

| Task | A2 design | Reps | A1 | A2 | A3 | Shape |
|---|---|---:|---:|---:|---:|---|
| audit_01–04, 06–08, 12 | rotated | 1 | 1.00 | 1.00 | 1.00 | single or flat requirements |
| audit_05 | a2b | 3 | 1.00 | 0.67 | 1.00 | `Visit(A)` ∧ `Triggered(A, WithinThen(B,1,2, Visit C))` |
| audit_09 | a2a | 3 | 1.00 | 0.33 | 1.00 | `Visit(A)` ∧ `Triggered(A, WithinThen(B,1,2, SafeUntil X C))` |
| audit_10 | a2c | 3 | 1.00 | 1.00 | **0.00** | `Ordered(A,B,C)` ∧ `SafeUntil(X,C)` |
| audit_11 | a2b | 3 | 1.00 | 1.00 | 0.67 | `Visit(A)` ∧ anchored chain ∧ `Triggered(C, SafeUntil X D)` |

## The seven failures are two errors

**Mode A — a standalone clause is dropped (4 of 7).** The card says "Pick up
at shelf A at least once" *and* gives a triggered rule about A. The author
writes the triggered rule and omits the standalone visit, so a trace with no
A at all is vacuously accepted. Seen in a2b (audit_05), a2a (audit_09 twice —
the two replicates are byte-identical), and a3 (audit_11). Never in LTLf,
where the same fact costs one conjunct: `F at_A & G(...)`.

**Mode B — independent requirements are coupled (3 of 7).** audit_10 asks
for `A → B → C` in order *and, separately,* "avoid X until C". All three
Haiku Python authors, independently, tied the until-check to the C they had
chosen as the ordered-sequence witness, instead of checking it against the
first C in the trace. The requirements are independent in the gold, the card
says "in addition", and the LTLf authors wrote them as two conjuncts three
times out of three. This is a stable, representation-specific error mode,
not sampling noise.

The failure taxonomy reported `other semantic error` for all seven, so the
§37 systematic-mode criterion did not fire. The taxonomy is too coarse to
separate these two modes; the gate passed on spread instead.

## What the audit did and did not test

**It did** validate the repaired apparatus end to end: the compositional IR
annotated every selected card (no candidate was excluded for
inexpressibility, unlike Pilot 1.1's three); every arm received sixteen
oracle-verified worked examples; prompt-side isolation passed; the run is
replayable from the committed cache; and `run_public.py` verifies 43 checks
without opening gold.

**It did not** test compositional out-of-distribution generalization. Under
the realism rule the Haiku curator produced tasks whose structures already
appear in training: **11 of 12 released tasks have
`unseen_composition_count = 0`**, and the one exception (audit_06,
`AnyOf→Ordered`) was solved by every arm. This is not a curation failure. It
is a property of the domain: ordinary warehouse operating requirements are
combinations that ordinary training cards also contain. Whether the
"compositional OOD" framing fits this domain at all is now an open question,
recorded in the reflection below rather than papered over.

## Support-material observation

Two of the five blind design-phase authors made the same convention error
before freeze: the A3 example author (3 of 16 monitors) and DSL designer A
(1 of 16 artifacts, plus a redundant `after` construct) read "after the
trigger, …" as *strictly after* where the public contract says evaluation
begins *at* the trigger step. Both were repaired in one round against a
counterexample; DSL designer C read it correctly and flagged the judgment in
its README; the A1 example author made no such error. All repairs happened
before any audit card was released and are recorded in
`freeze/a3_example_conformance.json` and the design A README.

## What changed from Pilot 1.1

| Defect in 1.1 | Fix in 1.2 |
|---|---|
| Gold `Within` bound a label; three of six high candidates unannotatable | `WithinThen(event, lo, hi, then)` — anchored continuation; zero exclusions |
| A1 reference showed `X^l p` notation; 68 % of A1 syntax failures copied it | Notation removed; nesting shown by example only |
| A2 got 14 worked examples, A1 and A3 got none | 16 oracle-verified examples per arm; `build_view` refuses to build a view without them |
| Author `llama3.2:3b` floored on "visit A" | Fresh memoryless Haiku subagents; every trial 100 % parse |
| 10 × 5 × 10 fixed grid | 12 tasks × 3 arms, A2 rotated by seeded permutation, +2 replicates only where arms disagreed: 60 trials |
| ≥3-task 20-point spread as the only gate | Spread retained; exact McNemar across tasks added and reported honestly as underpowered |
| Tasks written to be hard | Curator bound by a realism rule; each card carries a one-sentence operational purpose |

## Iteration accounting

Protocol §40: this run consumed **Pilot 1.2 iteration 1** and burned
`audit_01`–`audit_12` (curator `low_01`–`04`, `medium_01`–`04`,
`high_01`–`04`). The remaining pool holds `low_05`–`06`, `medium_05`–`06`,
`high_05`–`06`.

## Limitations

- Twelve tasks and one to three replicates per cell. The spread criterion is
  descriptive; the paired test has no power at this size.
- Eight of twelve tasks sit at 100 % for every arm. The signal lives in four
  tasks. A full benchmark needs more tasks of the anchored-continuation and
  independent-conjunction shapes — drawn by the same blind process, not
  written to target A2 or A3.
- One authoring model (Haiku). The A1 = 100 % result may be an interaction
  between LTLf's conjunctive surface and how this model reads a card; it is
  not a claim about human authors.
- A2 is three designs, each seen on four tasks. Between-design variance
  (a2a 67 %, a2c 100 %) is visible but not estimable.
- The failure taxonomy needs at least two new categories — *dropped
  standalone clause* and *coupled independent requirements* — before the
  systematic-mode criterion can do its job.

## Reproduction

```bash
python run_public.py         # 43 checks, no gold
python run_coordinator.py    # regenerate gold, suites, evaluation, gate
```

Authoring is not re-run; the 60 cached subagent responses are the measured
data. To author a new trial: `python -m author_harness.export_prompt <task>
<arm>` → hand the file to a fresh agent → `python -m
author_harness.ingest_trial <task> <arm> <replicate> <response>`.

## Result files

| File | Contents |
|---|---|
| `results/ambiguity_audit.csv` | pre-release audit, per task |
| `results/trials.csv` | 60 rows, one per artifact |
| `results/task_summary.csv` | per-task rates, majority outcomes, novelty metadata |
| `results/arm_summary.csv` | per-arm, per-design, and pooled-A2 rates |
| `results/paired_tests.csv` | exact McNemar across tasks, per arm pair |
| `results/failure_modes*.csv` | failure taxonomy |
| `results/discrimination_gate.json` | ceiling, floor, spread, paired tests, action |
| `results/metadata.json` | authoring channel, stage plan, freeze hashes, thresholds |
| `results/checksums.sha256` | digests of every published result file |
