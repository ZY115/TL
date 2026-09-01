# Temporal Logic vs. Handwritten Monitor

## Pilot 0.1 — Sequence Representation Benchmark

This repository is a methodology-calibration experiment. It does **not** test
whether Temporal Logic (TL) is generally better than handwritten code, and it
does not assume a winner.

The narrow research question is:

> Under fixed finite-trace semantics and fixed implementation conventions, how
> do task-specific representation size and structural edit footprint scale with
> sequence length for a TL formula, an explicit FSM, and a parameterized
> handwritten monitor?

Pilot 0.1 validates the semantic-equivalence pipeline, checks whether raw
representation metrics can be extracted reproducibly, exposes comparison-boundary
choices, and establishes infrastructure for later safety, timing, branching, and
compositional pilots. Those later structures are deliberately absent here.

## Scope

The only task family is

```text
S_n = A1 -> A2 -> ... -> An,  n = 1,...,10
```

Only sequence length changes. There is no obstacle avoidance, safety constraint,
bounded timing, branching, repeated-task requirement, reward, RL algorithm,
robot simulation, or task repair.

## Authoritative finite-trace semantics

A finite trajectory is `tau = (e0, e1, ..., e[T-1])`. For `S_n`, each time step
contains exactly one event from:

```text
{O, A1, A2, ..., An}
```

`O` is unrelated. Because one and only one event occurs at a step, two distinct
required propositions cannot be true simultaneously.

A trace is accepted iff there are strictly increasing indices
`i1 < i2 < ... < in` with `e[ik] = Ak`. Equivalently, the target list occurs as
an ordered subsequence.

Consequences:

- unrelated events are allowed: `[O, A1, O, A2, O, A3]` is accepted;
- repetitions are allowed: `[A1, A1, A2, A2, A3]` is accepted;
- a future target seen early is ignored rather than causing permanent failure:
  `[A2, A1, A2, A3]` is accepted;
- `[A2, A1, A3]` is rejected because no `A2` occurs after the valid `A1`;
- an empty or incomplete finite trace is rejected.

Runtime code may conceptually be in progress, but final benchmark output is only
Boolean: completed is `True`; not completed by trace end is `False`.

## Three first-class representations

### A. Finite-trace TL fragment

The fragment contains only `Atom`, `And`, and `Eventually (F)`. The canonical
formula for three targets is:

```text
F(A1 & F(A2 & F(A3)))
```

`src/tl/evaluator.py` implements `evaluate(formula, trajectory) -> bool`.
`F` includes the current position, as usual. Nested required atoms still occur
at strictly later steps because the trace model allows exactly one distinct event
per step.

> This is a finite-trace TL fragment implemented for this benchmark. It is not
> intended to be a complete LTL, STL, or MTL implementation.

No other TL operators are introduced.

### B. Explicit FSM

`src/explicit_fsm/generator.py` emits one Black-formatted Python monitor per
task. It contains explicit `WAIT_Ai` states, transition guards, destinations,
and `SUCCESS`. An event not expected in the current state leaves the state
unchanged. Semantic tests compile and execute the exact generated source.

The canonical style is the same for every `n`; it is intentionally ordinary,
not deliberately expanded or compressed.

### C. Parameterized handwritten monitor

The reusable engine in `src/parameterized/monitor.py` advances an index through
the target list. The task-specific representation is a counted source object:

```python
targets = ["A1", "A2", "A3"]
```

The list is never treated as free or hidden configuration. Semantic tests parse
the exact generated list source and pass it to the reusable engine.

## Independent semantic oracle

`src/oracle.py::sequence_oracle` directly scans for the ordered subsequence. It
does not call the TL evaluator, generated FSM, or parameterized engine. Every
tested trace is checked three ways:

```text
TL == oracle
explicit FSM == oracle
parameterized monitor == oracle
```

Any mismatch makes the run fail before construction or edit metrics are written.

## Deterministic semantic tests

For `n <= 4`, the runner exhaustively enumerates every trace over
`[O, A1, ..., An]` for lengths `0,...,n+2`.

For each `n = 5,...,10`, it generates exactly 20,000 deterministic traces:

| Category | Count | Purpose |
|---|---:|---|
| Uniform random | 4,000 | Unconstrained alphabet/length samples |
| Generated satisfying | 4,000 | Guaranteed ordered subsequences plus noise |
| Incomplete | 3,000 | A required target is absent |
| Early future target | 3,000 | Half recover later; half do not |
| Repeated targets | 3,000 | Half complete; half omit one target |
| Irrelevant events | 3,000 | `O`-heavy positive and negative traces |

The base seed is `20260831`. For sequence length `n`, the category seed is:

```text
20260831 + n*100 + category_index
```

Every concrete seed is saved in `results/semantics.csv`; the rule and category
counts are repeated in `results/metadata.json`.

The inserted-`X` variants also receive six deterministic smoke checks per `n`.
These checks validate generated modified sources but do not expand the
authoritative original-task testing scope or appear as extra benchmark rows.

## What is counted

The benchmark separates information that changes with `S_n` from reusable code.

| Representation | Task-specific representation | Reusable infrastructure |
|---|---|---|
| TL | Canonical formula text | AST classes, evaluator, generator |
| Explicit FSM | Complete canonical generated monitor source | Generator/compiler and runner utilities |
| Parameterized | Canonical `targets = [...]` source | Generic index-monitor algorithm |

All task-bearing source/configuration is counted. Reusable code is measured once
in `results/infrastructure.csv` and is not added to every task row.

The explicit FSM source includes its small function/loop shell because each
generated file is a self-contained explicit monitor. This fixed comparison
boundary is a documented methodology choice, not a claim that its tokens equal
TL tokens semantically. The normalized FSM tree separately removes incidental
Python syntax for task-level structural edit analysis.

## Canonical formatting and source metrics

Python task sources are formatted by Black with line length 88. TL uses one
deterministic pretty-printer. Every canonical source ends in one newline.

Common source measurements are:

- `characters`: exact Unicode code-point count, including the terminal newline;
- `lines`: physical lines from `splitlines()`;
- `tokens`: matches from the single language-neutral tokenizer in
  `src/metrics.py` (quoted strings, identifiers, integers, multi-character
  comparisons/arrows, and individual punctuation/operators).

The common tokenizer makes extraction deterministic. It does **not** make a TL
token and a Python token equal units of semantic meaning.

TL-specific metrics:

- total TL AST nodes;
- Atom, Eventually, and And counts;
- maximum AST depth, counting the root as depth 1.

Explicit-FSM metrics:

- states: all `WAIT_*` states plus `SUCCESS`;
- transitions: one expected-event transition per target;
- task-specific conditions: one event guard per transition (state ownership is
  represented by the containing control state rather than counted again);
- explicit task variables: the single `state` variable;
- branches: one `if`/`elif` transition branch per target;
- Python AST nodes, retained only as raw within-Python data.

Parameterized metrics:

- target-entry count;
- task-source characters, lines, and tokens.

AST or structural counts from different representation languages are not treated
as interchangeable units. There is no combined complexity score and no single
TL-vs-manual crossover curve in this pilot.

## Primary analysis

Every raw metric is saved as `M(n)`. For the shared token metric, the plot also
reports:

```text
Delta M(n) = M(n+1) - M(n)
```

This asks how much canonical task-specific source is added by one more ordered
subtask. Representation-specific structural metrics are shown in separate panels
instead of being collapsed into one score.

## Standardized modification

For every original `S_n`, let `p = ceil(n/2)` and insert `X` immediately after
`A_p`. For example:

```text
A1 -> A2 -> A3 -> A4
A1 -> A2 -> X -> A3 -> A4
```

For `n=1`, `A1` becomes `A1 -> X`.

The benchmark calls the resulting measurements **Structural Edit Footprint**.
They are canonical-representation diffs, not human modification effort,
maintenance cost, developer effort, or difficulty.

## Source edit definitions

Before and after source lines are compared with deterministic `SequenceMatcher`
opcodes and `autojunk=False`. The same procedure is applied to token sequences.

- insert/delete opcodes count inserted/deleted elements;
- for a replace block, paired old/new elements count as changed;
- any unpaired remainder counts as inserted or deleted.

The CSV preserves inserted, deleted, and changed components separately. A plot
also preserves the three token components separately; it does not convert them
into a human-effort estimate.

## Normalized trees and APTED

Tree distance is ordered APTED with unit costs:

```text
insert node = 1
delete node = 1
rename node = 1 (0 when labels are equal)
```

Only before/after trees of the **same representation** are compared.

TL tree:

```text
Eventually
└── And
    ├── Atom:A1
    └── Eventually
        └── ...
```

FSM tree:

```text
FSM
├── State:WAIT_A1
│   └── Transition
│       ├── Event:A1
│       └── Destination:WAIT_A2
└── ...
```

Parameterized tree:

```text
Sequence
├── A1
├── A2
└── ...
```

The explicit FSM additionally reports states/transitions/conditions added or
removed, existing transitions changed, and existing dependencies changed. A
destination change is one existing transition change and one existing dependency
change.

## Environment and installation

Target: macOS, Python 3.11 or newer, `venv`, pytest, pandas, matplotlib, Black,
and APTED. The completed reference run in this folder used:

| Component | Version |
|---|---:|
| Python | 3.12.13 |
| APTED | 1.0.3 |
| Black | 26.5.1 |
| matplotlib | 3.11.1 |
| pandas | 2.3.3 |
| pytest | 8.4.2 |

The top-level packages are pinned in `requirements.txt`, and the exact versions
observed by every completed run are also stored in `results/metadata.json`.

```bash
cd tl_sequence_pilot
/path/to/python3.11-or-newer -m venv .venv
source .venv/bin/activate
cd pilots/pilot_0_1_sequence
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pytest
python run_experiment.py
```

The complete experiment itself runs with one command after environment setup:

```bash
python run_experiment.py
```

It regenerates `generated/`, `results/`, and `plots/` from scratch. Timestamps
are deliberately omitted from result metadata so repeated runs in the same
environment produce identical CSVs.

## Outputs

```text
pilot_0_1_sequence/
├── README.md
├── requirements.txt
├── pyproject.toml
├── run_experiment.py
├── src/
├── tests/
├── generated/
│   └── S1 ... S10/
│       ├── original/
│       └── modified_insert_X/
├── results/
│   ├── construction.csv
│   ├── structural_edit.csv
│   ├── semantics.csv
│   ├── infrastructure.csv
│   ├── metadata.json
│   └── checksums.sha256
└── plots/
```

Required plots are generated separately:

- construction tokens;
- representation-specific structural metrics;
- marginal token increment;
- normalized-tree edit distance;
- inserted/deleted/changed token components.

No plot is labeled human effort, maintenance difficulty, overall complexity, or
a combined TL-vs-manual complexity score.

## Interpretation boundary

It is plausible that TL formula size, explicit-FSM size, and parameter-list size
are all approximately linear in `n`, while insertion has constant-sized
normalized-tree edits. That would be a valid result: pure sequence length alone
may not create a strong representational advantage for TL. It would motivate
later, separately designed safety, timing, branching, and interaction pilots.

The generated data should therefore be read as calibration evidence about these
fixed representations and metrics—not as a general ranking of TL and handwritten
code.
