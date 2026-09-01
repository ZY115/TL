# Temporal Logic vs. Handwritten Monitor

## Pilot 0.3 — Branch-Dependent Temporal Obligations

Pilot 0.3 is a methodology-calibration benchmark. It asks:

> Under fixed finite-trace semantics and fixed implementation conventions, how
> do task-specific representation size and structural edit footprint change as
> the number of branch-dependent bounded temporal obligations increases?

It compares a finite-trace bounded temporal-logic (TL) formula, a canonical
explicit conditional timed monitor, and a first-class parameterized handwritten
monitor. It is **not** a general test of TL superiority, human effort,
maintainability, or runtime.

## Task family

The independent variable is the number of conditional stages, `k = 0,...,6`.
Every trace starts with `S`, completes exactly one decision per stage in stage
order, fulfills the goal activated by that decision, and ends with `E` only
after all selected goals are complete.

For stage `i`:

- selecting `Li` activates `Pi` with inclusive distance `1...8`;
- selecting `Ri` activates `Qi` with inclusive distance `1...10`;
- exactly one of `Li` and `Ri` may occur;
- selected goals may complete in any order;
- an unselected goal is irrelevant;
- a goal before its activating choice does not count.

Each time step has exactly one event. `O` is irrelevant and repeatable; every
other named event may occur at most once. Final evaluation is Boolean.

For `k=0`, the task is simply `S` followed eventually by `E`.

## Three representations

### Finite-trace bounded TL

The implemented fragment contains only:

```text
Atom, Not, And, Or, Eventually, Always, Implication, BoundedEventually
```

The decision skeleton is a nested eventual sequence of `(Li | Ri)` clauses.
Each stage also has two exclusivity clauses and two conditional obligations:

```text
G(Li -> G(!Ri))
G(Ri -> G(!Li))
G(Li -> F[1,8](Pi & F(E)))
G(Ri -> F[1,10](Qi & F(E)))
```

This is a finite-trace bounded temporal-logic fragment defined for this
benchmark. It is not a complete LTL, STL, or MTL implementation.

### Explicit conditional timed monitor

The generated Python monitor uses explicit stage control plus, for every stage,
one selection variable, one start timestamp, and one completion flag. The two
branch paths and both deadline checks are written explicitly. It stores start
indices; it does not use artificial countdown loops.

### Parameterized handwritten monitor

The task-specific representation is a canonical list of stage descriptors:

```python
STAGES = [
    ("L1", "P1", 8, "R1", "Q1", 10),
]
```

A reusable generic engine interprets this schema. This is a full baseline, not
an optional check. The descriptor list is counted as task-specific
representation; the engine is reported once as reusable infrastructure.

## Independent semantic oracle

`src/oracle.py` directly implements the mathematical definition. It checks the
trace start/end, uniqueness, exactly one decision per stage, decision order,
selected-goal position, inclusive bound, and completion before `E`. It calls
none of the three compared implementations.

Every tested trajectory must satisfy:

```text
TL result            == oracle
explicit result      == oracle
parameterized result == oracle
```

If any mismatch occurs, the runner writes semantic diagnostics and stops before
exporting construction or edit metrics.

## Semantic test suite

For each applicable `k`, deterministic groups cover:

1. all `2^k` branch assignments using the overlapping-obligation stress trace;
2. exact left/right deadline and one step beyond it for every stage;
3. missing decisions;
4. both branches at one stage;
5. adjacent decision-order swaps;
6. missing selected goals;
7. wrong/unselected goals only;
8. selected goals before their choice;
9. early `E`;
10. successful goal reordering.

For `k=1,...,6`, the runner also creates 10,000 deliberately mixed positive
and negative structured-random traces using seed `20260901 + k`.

### Documented `k=6` reverse-order boundary

The requested fully reversed goal order cannot be successful at `k=6` under
the fixed bounds. With six decisions first, `R1` is at position 1 and `Q1` is at
position 12, so their distance is 11 and violates the right bound 10. The
benchmark therefore:

- keeps the original bounds unchanged;
- includes the full reversal as a deterministic deadline-failure witness;
- uses goal order `6,5,4,1,2,3` as a successful non-stage-order witness.

For `k<=5`, the fully reversed selected-goal order remains the success test.

## Measurement boundary

Task-specific versus reusable components are separated as follows:

| Representation | Task-specific | Reusable infrastructure |
|---|---|---|
| TL | formula | syntax, evaluator, generator |
| Explicit | generated explicit monitor | generator/compiler and benchmark utilities |
| Parameterized | stage descriptor list | generic conditional deadline engine |

No task information is hidden in an uncounted configuration.

## Raw metrics

No combined complexity score is produced.

All task-specific sources record canonical characters, lines, and lexical
tokens. TL additionally records AST node/operator counts, depth, decision stages,
four implication-based branch clauses per stage, and two bounded obligations per
stage. The explicit
monitor records control, variable, branch, condition, mapping, and deadline
bookkeeping counts plus raw Python AST nodes. The parameterized representation
records stage, branch, goal-mapping, bound, and task-field counts.

Python sources are formatted with Black at line length 88. TL uses a deterministic
pretty-printer. Source edits use `SequenceMatcher(autojunk=False)`.

Normalized ordered trees describe task structure rather than incidental parser
syntax. Tree edit distance uses APTED with unit insert, delete, and rename costs.
Distances compare only before/after trees of the **same** representation. A TL
tree-edit unit is not assumed equal to a Python or parameter-tree unit.

## Modification experiments

### Stage addition

For `k=0,...,5`, compare `B_k` with canonical `B_(k+1)`. The exact change is one
new conditional stage with two branches, two goal mappings, and two bounds.

### Branch rewire

For `k=1,...,6`, choose `q = ceil(k/2)` and change only the left selected goal:

```text
Pq -> Xq
```

The old-goal failure, new-goal success, and unchanged right branch are all
verified against the modified oracle before edit metrics are accepted.

These metrics are called **structural edit footprint**. They do not measure
developer time, cognitive load, error probability, or maintenance difficulty.

## Reproduce

Requirements: macOS or another Python environment with Python 3.11+, plus the
exact packages pinned in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
python run_experiment.py
```

The final command regenerates all representations, semantic results, edit
measurements, metadata, checksums, and plots. Output files are deterministic for
the same Python/package environment and seeds.

## Current validated result

The checked run used Python 3.12.13 and evaluated 61,219 trajectories per
representation across base and modified variants. All mismatch counts are zero.

The raw construction results are approximately linear:

- TL tokens: `6, 95, 184, 273, 362, 451, 540`;
- explicit monitor tokens: `74, 175, 278, 381, 484, 589, 692`;
- parameterized configuration tokens: `4, 18, 32, 46, 60, 74, 88`.

The parameterized schema is smallest in this canonical setup. Adding one stage
has a constant normalized tree edit within each representation (TL 37, explicit
17, parameterized 9), while absolute distances are not cross-language units.
Rewiring one selected goal changes one lexical token and has normalized tree
edit distance 1 in all three representations.

The appropriate interpretation is limited: this regular conditional/timing
family is captured especially compactly by a small handwritten schema, and the
branch rewire is equally local under the measured structural representation.
It does not establish a general winner.

## Outputs

- `results/construction.csv`: raw construction measurements.
- `results/semantics.csv`: all oracle-match counts and seeds.
- `results/stage_add_edit.csv`: stage-add structural edit footprint.
- `results/branch_rewire_edit.csv`: branch-rewire structural edit footprint.
- `results/infrastructure.csv`: reusable code sizes reported once.
- `results/metadata.json`: semantics, versions, seeds, and design decisions.
- `results/checksums.sha256`: deterministic result-file checksums.
- `generated/B0` ... `generated/B6`: sources and normalized trees.
- `plots/`: separate construction and edit plots; no aggregate score.
