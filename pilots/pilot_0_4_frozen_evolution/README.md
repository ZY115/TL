# Temporal Logic vs. Specialized Handwritten DSL

## Pilot 0.4 — Frozen-Abstraction Requirement Evolution

Pilot 0.4 asks:

> When one fixed task accumulates heterogeneous temporal requirements, how
> much author-facing task source and representation-system infrastructure must
> change in an existing general TL stack and an existing specialized DSL?

This is a methodology-calibration experiment. It does not measure developer
time, comprehension, maintainability, cognitive load, or software quality, and
it does not assume that TL wins.

## Fairness boundary

**The TL system begins with a broader temporal operator vocabulary than the
specialized DSL. Pilot 0.4 therefore does not compare equal-sized initial
systems. Instead, it measures the tradeoff between greater initial generality
and later representation-system evolution.**

The TL baseline contains the Pilot 0.3B base macros, a generic `RULE <Core TL>`
interface, and `Atom`, `Not`, `And`, `Or`, `Eventually`, `Always`,
`Implication`, and `BoundedEventually`. The specialized baseline contains only
the frozen Pilot 0.3B `STAGES` schema and its interpreter. Neither system is
redesigned from scratch after E0. A system snapshot may implement only
capabilities needed through that step.

The generic TL parser and `RULE` composition existed before E1. Their complete
files are exposed separately in `results/baseline_initialization.csv`; they are
not hidden in later evolution churn. Because Pilot 0.3B and Pilot 0.4 organize
their modules differently, the file also reports the full previous and current
TL infrastructure sizes and labels the new parser/system files as a
conservative initialization boundary instead of pretending that a mechanical
whole-directory diff isolates only `RULE`.

## Fixed B4 semantics

All tasks retain four Pilot 0.3B stages. At stage `i`, exactly one of `Li` and
`Ri` occurs. `Li` activates `Pi` within inclusive distance 1–8; `Ri` activates
`Qi` within inclusive distance 1–10. Decisions occur in stage order, selected
goals may finish in any order, unselected goals are irrelevant, and the unique
`E` is after every selected obligation. Every time step is one event. `O` may
repeat; every named non-`O` event occurs at most once.

The task ends at its unique `E`. Thus the declared E1 scope “no `BAD` before
successful completion” and the canonical `G(!BAD)` rule agree on every
benchmark trajectory.

## Pre-registered cumulative evolution

| Step | Added requirement | TL evolution | Specialized-DSL evolution |
|---|---|---|---|
| E0 | fixed B4 branch timing | frozen base + generic `RULE` initialization | frozen `STAGES` |
| E1 | global `BAD` avoidance | task source only | add `GLOBAL_AVOID` |
| E2 | `L2 -> P2 -> Z2 -> E` | task source only | add arbitrary-length `BRANCH_POST_SEQUENCES` |
| E3 | optional `H -> REC` within 1–3, before `E` | task source only | add `BOUNDED_RESPONSES` |
| E4 | if `R3`, avoid `Y3` until `Q3` (strong Until) | add only `Until` | add `AVOID_UNTIL` |
| E5 | `L4 -> P4 -> N1 -> N2 -> E` | task source only | reuse E2; infrastructure is byte-identical to E4 |
| E6 | if `J`, `C` within 2 or `D` within 5, before `E` | task source only | add `ALTERNATIVE_BOUNDED_RESPONSES` |

The exact expectations were frozen in `capability_matrix.csv`. No
requirement-specific TL macros, arbitrary DSL callback, or future operator is
allowed. TL gains strong `Until` only at E4.

## Independent semantics and tests

`src/oracle.py` directly implements B4 and every cumulative requirement. It
does not call either tested system. Its diagnostic form reports one Boolean per
active requirement and `None` for future requirements.

Every E0–E6 task is checked with:

- the Pilot 0.3B B4 deterministic regression families;
- deterministic boundary/inactive-branch cases for the new requirement;
- a satisfying and a current-requirement-only violating trace for every
  earlier/current requirement pair;
- 10,000 constructive structured-random traces with seed `20260910 + step`.

For E1–E6 the random distribution is 4,000 valid, 2,000 B4-invalid, and 4,000
single-evolved-requirement violations, approximately balanced among active
requirements. E0 has no evolved requirement to violate, so its documented
distribution is 4,000 valid and 6,000 B4-invalid. Positive traces are built
constructively; every controlled mutation is accepted only when oracle
diagnostics show that exactly the intended requirement failed.

Every system version also runs every earlier E0–Ei task source unchanged and
the immutable 12-spec Pilot 0.3B portfolio (`B1...B6`, base and branch rewire).
Any mismatch or regression aborts the experiment before conclusions are
exported.

## Measurement boundary

No weighted complexity or break-even score is produced.

- **Task-source layer:** characters, lines, lexical tokens, and deterministic
  source diffs. Token churn is inserted + deleted + changed tokens.
- **Infrastructure layer:** complete current size, files touched, line/token
  diffs, and ordered APTED distance over normalized Python ASTs with unit
  insert/delete/rename costs.
- **Validation layer:** validation-manifest diffs and regression counts,
  reported separately.
- **Migration layer:** old specifications requiring source migration and their
  source diffs.
- **Capability growth:** a descriptive count of semantic capability classes;
  the classes are not assumed to have equal power.

All source diffs use `SequenceMatcher(autojunk=False)`. AST distance is only a
within-language before/after measure; it is not a common TL-versus-Python unit.
Source size and lexical edit volume are not human effort.

## Repository map

```text
pilot_0_4_frozen_evolution/
├── capability_matrix.csv
├── systems/{tl,specialized_dsl}/E0...E6/
├── tasks/E0...E6/{tl.task,dsl.py}
├── legacy/                  # 12 immutable Pilot 0.3B specifications
├── src/                     # oracle, generators, metrics, compatibility, plots
├── tests/
├── results/
└── plots/
```

`systems/` retains the actual executable snapshots. `validation.py` belongs to
the validation layer and is excluded from infrastructure diffs.

## Reproduce

From the repository root after installing the pinned requirements:

```bash
source .venv/bin/activate
cd pilots/pilot_0_4_frozen_evolution
python run_experiment.py
pytest
```

Or run all pilots with `python run_all.py`. Python 3.11+ is required. Exact
Python/package versions, source-pilot commit, seeds, assumptions, and frozen
older-output hashes are recorded in `results/metadata.json`; generated files
are covered by `results/checksums.sha256`.

## Validated run

The current canonical run evaluated 76,142 semantic cases in the exported
rows, including 10,000 structured-random trajectories at every step and the
legacy regressions. Both systems have zero oracle mismatches. Every one of the
12 legacy specifications passed under every snapshot, every earlier evolution
source executed unchanged, and the measured migration count is zero.

| Outcome at E6 | General TL stack | Specialized DSL |
|---|---:|---:|
| E0 infrastructure tokens | 2,136 | 438 |
| E6 infrastructure tokens | 2,303 | 769 |
| E1–E6 infrastructure-changing steps | 1 | 5 |
| E1–E6 infrastructure-free steps | 5 | 1 |
| cumulative infrastructure token churn | 173 | 341 |
| cumulative task-source token churn | 122 | 80 |
| cumulative infrastructure files touched | 5 | 10 |
| task migrations | 0 | 0 |

The checkpoints behave as pre-registered: TL changes five implementation files
at E4 to add strong `Until`; the DSL changes two files at each of E1, E2, E3,
E4, and E6; both E4→E5 infrastructure diffs are exactly zero. The compact DSL
still has the smaller author-facing cumulative task edit footprint and the much
smaller initial infrastructure. The broader TL stack has fewer later
infrastructure-changing steps on this path. These are separate raw findings,
not one overall winner.

## How to interpret the result

Read these three trajectories first:

1. current infrastructure size;
2. cumulative infrastructure lexical edit volume;
3. cumulative task-source lexical edit volume.

If TL has fewer later infrastructure changes, the defensible claim is limited
to this pre-registered path: its broader initial operator set covered more of
these heterogeneous requirements. If E5 costs no DSL infrastructure change,
that is evidence that a capability-specific DSL extension can be amortized and
reused. Neither observation establishes universal maintainability or TL
superiority.
