# Temporal Logic vs. Handwritten Monitor

## Pilot 0.2 — Overlapping Bounded-Timing Dependencies

Pilot 0.2 is a methodology-calibration experiment. It does **not** test general
Temporal Logic (TL) superiority, does not assume a crossover exists, and does not
encode an expected winner.

The research question is:

> Under fixed finite-trace semantics and fixed implementation conventions, how
> do task-specific representation size and structural edit footprint change as
> the number of overlapping bounded timing constraints increases for a
> bounded-TL specification, an explicit timed monitor, and a parameterized
> handwritten deadline monitor?

Pilot 0.1 already calibrated pure ordered-sequence growth. Pilot 0.2 therefore
holds sequence length fixed and varies only the number of overlapping deadlines.

## Pilot 0.1 preservation

Pilot 0.2 lives entirely in `pilot_0_2_timing/`. It does not import, regenerate,
delete, or overwrite Pilot 0.1 outputs. The following SHA-256 values were recorded
immediately before Pilot 0.2 work began and are checked again after completion:

| Pilot 0.1 file | Pre-Pilot-0.2 SHA-256 |
|---|---|
| `results/construction.csv` | `0ca53f3d8e72eee7ad39e88ef361e1570d80036de0cb0707696bcd25b556d1af` |
| `results/structural_edit.csv` | `8682e4f13ecb0104e9b1760a5baea021847193d95957cf4d79634ebbeb00c384` |
| `results/semantics.csv` | `7733bd0b8162e2ff51017e039ee0da5c0cdcbc6d4ee6efa10e3e09f894c7daee` |
| `results/infrastructure.csv` | `3cec27cef1d89352a0ed2c00d7a289fb341289e100a477589dee37b493a5495a` |
| `results/metadata.json` | `0d22efa0154149bebf971f5d362564c543ade3b15dc908ca6cfb229a4c28e83d` |

The post-run verification produced the same five hashes exactly.

The language-neutral tokenizer, canonical `SequenceMatcher` diff, and unit-cost
APTED implementation are copied from Pilot 0.1 without semantic changes. Copies
are kept locally so Pilot 0.2 can run independently.

## Controlled task family

Every task uses the fixed base sequence:

```text
A1 -> A2 -> A3 -> A4 -> A5 -> A6 -> A7 -> A8 -> A9 -> A10
```

Sequence length is always 10. The only independent variable is `m`, the number
of active timing constraints, for `m = 0,...,5`:

```text
C1: A1 -> A6 within 8 steps
C2: A2 -> A7 within 8 steps
C3: A3 -> A8 within 8 steps
C4: A4 -> A9 within 8 steps
C5: A5 -> A10 within 8 steps
```

`T0` contains no timing constraint. `Tm` contains exactly `C1,...,Cm`.
The bound is inclusive: a position difference of 8 satisfies; 9 violates.

These dependencies overlap. After A1 through A5 have occurred and before A6,
up to five start milestones have been recorded while their corresponding end
milestones are still pending.

## Trace model and exact semantics

A finite trace is `tau = (e0,...,e[T-1])`. Every step contains exactly one event
from:

```text
{O, A1, A2, ..., A10}
```

`O` is irrelevant and may repeat. Each target event `A1,...,A10` may occur at
most once. This is an intentional difference from Pilot 0.1, where required
events could repeat. The restriction removes ambiguity about which occurrence
starts or completes a deadline and isolates timing structure.

A successful trace contains all ten targets in strict order at positions
`i1 < ... < i10`. For active constraint `Cj`, it must also satisfy:

```text
i[j+5] - i[j] <= 8
```

Missing targets and order violations fail. The benchmark only evaluates traces
inside the one-event-per-step, unique-target input model; the oracle additionally
rejects duplicate target events defensively.

## Representation A: finite-trace bounded temporal logic

The fragment contains only:

```text
Atom
And
Eventually F
Always G
Implication ->
BoundedEventually F[a,b]
```

The base sequence remains nested Eventually:

```text
F(A1 & F(A2 & ... F(A10)))
```

Each deadline is:

```text
G(Aj -> F[1,8](A[j+5]))
```

The full task is the base sequence conjoined with `C1,...,Cm`. The AST uses a
deterministic binary left fold in constraint order. The deterministic pretty
printer flattens only this top-level conjunction and emits one conjunct per line.

Exact finite-trace semantics at position `t`:

- `F phi` is true iff `phi` is true at some `u` in `[t,T-1]`;
- `G phi` is true iff `phi` is true at every `u` in `[t,T-1]`;
- `F[a,b] phi` is true iff `phi` is true at some in-trace position
  `u` with `t+a <= u <= t+b`;
- implication uses ordinary Boolean semantics.

For this pilot, `a=1` and the original upper bound is `b=8`.

> This is a finite-trace bounded temporal-logic fragment implemented for this
> benchmark. It is not a complete STL, MTL, or LTL implementation.

## Representation B: explicit timed monitor

Each generated monitor is a self-contained Black-formatted Python function with
the explicit phases:

```text
WAIT_A1, ..., WAIT_A10, SUCCESS
```

For every active constraint it declares one explicit timestamp variable such as
`start_C1`. The variable is assigned when the corresponding start event is
accepted. At the corresponding end event it checks:

```python
if start_C1 is None or step - start_C1 > 8:
    return False
```

No artificial per-step countdown loop is used. The implementation stores the
start step because that is the simpler normal handwritten style. The exact
generated source—not an uncounted external table—is compiled for semantic tests
and counted as the task-specific representation.

## Representation C: parameterized handwritten deadline monitor

The full counted task configuration contains both the fixed sequence and active
deadline tuples:

```python
targets = [
    "A1",
    # ...
    "A10",
]
timing_constraints = [
    ("A1", "A6", 8),
    ("A2", "A7", 8),
]
```

The reusable engine records accepted milestone positions and evaluates
`positions[end] - positions[start] <= bound`. This is a first-class strong
handwritten baseline. It is not deliberately weakened or treated as an optional
robustness check.

## Independent oracle

`src/oracle.py::timed_sequence_oracle` independently:

1. filters target events and verifies that they equal `A1,...,A10` exactly;
2. rejects duplicated target events;
3. builds the unique target-position map;
4. checks each active tuple directly with `position(end)-position(start)<=bound`.

It does not call the TL evaluator, explicit monitor, or parameterized engine.
For every tested trace:

```text
bounded TL == oracle
explicit timed monitor == oracle
parameterized deadline monitor == oracle
```

Any mismatch stops the run before construction or edit metrics are written.

## Deterministic semantic suites

### Main gap enumeration

Let `g1,...,g9` be the number of `O` events between adjacent targets. The runner
enumerates every vector in:

```text
{0,1,2}^9
```

This creates exactly `3^9 = 19,683` traces for every `Tm`, or 118,098 main gap
evaluations per representation over `m=0,...,5`.

For `Cj`, the position difference is:

```text
5 + sum(g[j] ... g[j+4])
```

It ranges from 5 to 15, systematically including values below 8, exactly 8,
exactly 9, large violations, and multiple overlapping violations.

### Sequence-failure tests

For every `Tm`, the runner also tests:

- each of ten targets removed individually: 10 traces;
- each adjacent target pair swapped: 9 traces.

All 19 traces must be rejected.

### Modified implementations

Every constraint-addition variant and every numeric-bound variant is independently
evaluated on the same 19,683 gap traces plus all 19 sequence-failure traces.
Edit metrics are not written for an unverified modified implementation.

## Representation boundary

| Representation | Counted task-specific object | Reusable infrastructure |
|---|---|---|
| Bounded TL | Complete canonical formula | AST classes, evaluator, generator |
| Explicit timed | Complete generated monitor source | Generator/compiler and runner utilities |
| Parameterized | Canonical `targets` and `timing_constraints` source | Generic sequence/deadline engine |

`src/model.py` is the benchmark task-family definition and is reported once in
`infrastructure.csv`. It does not replace any counted task representation: all
targets, endpoints, and bounds are repeated explicitly in each generated source
where that representation requires them.

## Construction metrics

There is no combined complexity score.

Common source metrics use the unchanged Pilot 0.1 conventions:

- exact characters, including the terminal newline;
- physical source lines;
- tokens from one deterministic language-neutral tokenizer.

Token counts are a common syntactic measurement, not proof that one TL token and
one Python token carry equal semantic meaning.

Bounded-TL structural fields:

- total AST nodes;
- Atom, And, Eventually, Always, Implication, and BoundedEventually counts;
- maximum node-level AST depth, root at depth 1;
- active timing-constraint count.

Explicit timed-monitor fields:

- 11 explicit control states and 10 sequence transitions;
- 10 sequence branches;
- task-specific conditions: 10 expected-event guards plus one compound deadline
  condition per active constraint;
- task-specific variables: one state variable plus one timestamp per constraint;
- timing variables, start assignments, deadline checks, and numeric bound
  occurrences, each recorded separately;
- Python AST nodes as raw within-Python data only.

Loop variables such as `step` and `event` are reusable control machinery, not
task-specific variables.

Parameterized fields:

- target count;
- active timing-constraint count;
- constraint-field count, defined as three fields `(start,end,bound)` per tuple;
- common characters, lines, and tokens of the complete counted configuration.

The primary analysis keeps every `M(m)` raw and computes token marginal growth:

```text
Delta M(m) = M(m+1) - M(m)
```

Structural measurements from different representation languages are not merged
or interpreted as equal semantic units.

## Modification A: add one constraint

For `m=0,...,4`, the canonical task `Tm` is compared with a freshly generated
variant containing exactly `C1,...,C[m+1]`. The variant source is asserted equal
to canonical `T[m+1]` source.

The **Constraint-Addition Structural Edit Footprint** records canonical line and
token edit components, same-representation tree edit distance, constraints added,
and explicit timing variables/start rules/deadline checks added or removed.

## Modification B: change one numeric bound

For every `m=1,...,5`, set `q=ceil(m/2)` and change only `Cq` from bound 8 to
bound 6. The **Numeric-Bound Structural Edit Footprint** records the same source
and tree measurements, the changed bound, and—only for the explicit monitor—the
existing deadline check changed.

Neither modification is labeled human maintenance effort, developer effort,
difficulty, comprehension, cognitive load, or error probability.

## Canonical source diff

Python sources use Black with line length 88. TL uses its deterministic printer.
Every source ends in one newline.

Canonical before/after line sequences and token sequences are compared with
`SequenceMatcher(autojunk=False)`:

- insert/delete opcodes count inserted/deleted elements;
- paired elements in a replacement block count as changed;
- unmatched replacement remainders count as inserted or deleted.

Inserted, deleted, and changed components remain separate raw fields.

## Normalized trees and APTED

Ordered APTED uses unit costs: insert 1, delete 1, rename 1, equal label 0. Only
before/after trees of the same representation are compared.

Bounded-TL uses the actual AST. One timing subtree is:

```text
Always
└── Implies
    ├── Atom:A1
    └── BoundedEventually[1,8]
        └── Atom:A6
```

The normalized explicit tree removes incidental Python syntax:

```text
TimedMonitor
├── Sequence
│   ├── State:WAIT_A1
│   │   └── Transition:A1->WAIT_A2
│   └── ...
└── Timing
    ├── Constraint:C1
    │   ├── Start:A1
    │   ├── End:A6
    │   ├── Bound:8
    │   ├── StartVariable:start_C1
    │   ├── TimingStartRule
    │   └── DeadlineCheck
    └── ...
```

The normalized parameter tree is:

```text
Task
├── Sequence
│   ├── A1
│   └── ... A10
└── Timing
    ├── Constraint
    │   ├── Start:A1
    │   ├── End:A6
    │   └── Bound:8
    └── ...
```

Tree distances remain within-representation edit measurements. A TL distance is
never compared with a Python parser AST as if they were semantic equivalents.

## Environment and reproduction

The reference environment is macOS with:

| Component | Version |
|---|---:|
| Python | 3.12.13 |
| APTED | 1.0.3 |
| Black | 26.5.1 |
| matplotlib | 3.11.1 |
| pandas | 2.3.3 |
| pytest | 8.4.2 |

Top-level packages are pinned in `requirements.txt`; every run records observed
versions in `results/metadata.json`.

Fresh setup:

```bash
cd tl_sequence_pilot
python3.11 -m venv .venv
source .venv/bin/activate
cd pilots/pilot_0_2_timing
python -m pip install -r requirements.txt
pytest
python run_experiment.py
```

After environment setup, the complete experiment runs from one command:

```bash
python run_experiment.py
```

It deterministically regenerates only this folder's `generated/`, `results/`, and
`plots/`. Timestamps are omitted from metadata so repeated runs in one environment
produce byte-identical result files.

## Outputs

```text
pilot_0_2_timing/
├── README.md
├── requirements.txt
├── pyproject.toml
├── run_experiment.py
├── src/
├── tests/
├── generated/
│   ├── T0/
│   ├── ...
│   └── T5/
├── results/
│   ├── construction.csv
│   ├── semantics.csv
│   ├── constraint_add_edit.csv
│   ├── numeric_bound_edit.csv
│   ├── infrastructure.csv
│   ├── metadata.json
│   └── checksums.sha256
└── plots/
```

Separate plots cover:

- task-specific tokens;
- bounded-TL structural metrics;
- explicit timed-monitor structural metrics;
- parameterized configuration metrics;
- marginal token growth;
- constraint-addition tree and token edits;
- numeric-bound tree and token edits.

No plot is an aggregate TL-versus-handwritten complexity score.

## Completed reference-run results

The completed run evaluated 118,098 base-task gap traces per representation and
196,830 modified-task gap traces per representation. Including deterministic
sequence failures, each representation was checked on 315,232 trace/task pairs.
All bounded-TL, explicit, and parameterized results matched the independent
oracle; every mismatch count is zero.

Task-specific lexical tokens were:

| Representation | `m=0` | `m=5` | Marginal tokens per added constraint |
|---|---:|---:|---:|
| Bounded TL | 49 | 124 | 15 |
| Explicit timed monitor | 143 | 238 | 19 |
| Parameterized deadline monitor | 28 | 68 | 8 |

Under the fixed normalized trees, adding one constraint had constant distance:

| Representation | Tree edit distance | Inserted source tokens |
|---|---:|---:|
| Bounded TL | 6 | 15 |
| Explicit timed monitor | 7 | 19 |
| Parameterized deadline monitor | 4 | 8 |

For the numeric `8 -> 6` modification, all three representations had tree edit
distance 1 and exactly one changed token, with no inserted or deleted token.

This resembles the specification's possible Outcome A: bounded TL reduces some
explicit timestamp bookkeeping relative to direct generated branches, while the
well-designed parameterized handwritten abstraction remains the smallest under
the shared lexical-token metric. This is not a general TL ranking. The result is
sensitive to the counted representation boundary and does not make tokens from
different languages semantically interchangeable.

## Interpretation boundary

Several outcomes are valid: explicit bookkeeping may grow faster while the
parameterized baseline stays compact; TL and parameterized configuration may grow
similarly; all three may be similar; or metrics may prove highly sensitive to the
chosen representation style. Pilot 0.2 is intended to identify which situation
occurs under these fixed conventions, not to force a TL victory.

The benchmark contains no RL training, rewards, PPO, robot dynamics, continuous
state, STL robustness, runtime benchmark, task-success probability, task repair,
or human-subject measurement.
