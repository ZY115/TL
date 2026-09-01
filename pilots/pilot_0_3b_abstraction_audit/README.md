# Temporal Logic vs. Handwritten Abstractions

## Pilot 0.3B — Abstraction-Level Fairness Audit

Pilot 0.3B audits the comparison boundary used in Pilot 0.3. It introduces no
new task semantics. Its exact research question is:

> For the same Pilot 0.3 task family and semantics, how do author-facing
> representation size and structural edit footprint change when Core TL is
> compared with a reusable macro-based TL representation, the existing
> parameterized handwritten DSL, and the explicit handwritten monitor?

The secondary question is how much representation compression comes from a
reusable abstraction itself, independently of whether that abstraction is
implemented with TL or Python.

This is not a TL-superiority experiment and does not measure human
comprehension, developer time, error rate, cognitive effort, or maintenance
difficulty.

## Unchanged task semantics

The benchmark reuses Pilot 0.3 tasks `B0,...,B6` exactly. For every stage `i`:

```text
Li selects Pi within inclusive distance 1...8
Ri selects Qi within inclusive distance 1...10
```

Exactly one branch occurs at each stage, decisions occur in stage order,
selected goals may complete in any order, unselected goals are irrelevant, and
`E` occurs only after all decisions and selected obligations finish. Each step
contains one event; `O` may repeat; every named non-`O` event may occur at most
once.

The documented `k=6` boundary is preserved: a complete goal reversal is a
deadline-failure witness because `R1 -> Q1` has distance 11, while goal order
`6,5,4,1,2,3` is the satisfiable non-stage-order witness. Bounds were not
changed.

## Fair comparison boundary

| Representation | Author-facing abstraction | Reusable infrastructure | Counted task information | Environment validation |
|---|---|---|---|---|
| Core TL | primitive temporal operators | Core-TL evaluator | formula | shared validator |
| Macro TL | `ORDERED_CHOICES` and `TIMED_CHOICE_STAGE` | macro expander + Core-TL evaluator | macro calls | shared validator |
| Explicit monitor | direct state and branch logic | Python runtime | generated task monitor | shared validator |
| Parameterized DSL | six-field stage descriptor | generic stage interpreter | `STAGES` list | shared validator |

The machine-readable version is `results/baseline_fairness.csv`.

Pilot 0.3 placed named-event uniqueness checks inside the two Python
implementations while TL relied on the trace-model assumption. Pilot 0.3B moves
legal-alphabet and uniqueness checks into the common
`validate_trace_model(trajectory, alphabet)` infrastructure. All four methods
receive only validated traces, and validator code is excluded from task-source
size.

## Four first-class representations

### Core TL

The Core-TL syntax, generator, evaluator, and formula formatting are copied from
Pilot 0.3 without simplification. For every base task, the generated formula is
automatically checked byte-for-byte against Pilot 0.3.

### Macro TL

The deterministic author-facing form is:

```text
START(S)
ORDERED_CHOICES(
    (L1 | R1),
    (L2 | R2)
)
TIMED_CHOICE_STAGE(L1, P1, 8, R1, Q1, 10)
TIMED_CHOICE_STAGE(L2, P2, 8, R2, Q2, 10)
END(E)
```

`TIMED_CHOICE_STAGE(L,P,bL,R,Q,bR)` expands to exactly:

```text
G(L -> G(!R))
G(R -> G(!L))
G(L -> F[1,bL](P & F(E)))
G(R -> F[1,bR](Q & F(E)))
```

`ORDERED_CHOICES` expands to the same nested decision formula used by Pilot
0.3. Macro TL is therefore an author-facing abstraction over Core TL, not a new
logic or new semantics.

For every base and modified task, the runner requires:

```text
direct Core-TL AST == Macro-TL expanded AST
```

It saves both the Macro-TL surface source and expanded Core-TL source.

### Explicit monitor

The Pilot 0.3 strategy is preserved: every stage has explicit selection,
timestamp, completion state, decision branches, goal branches, and deadline
checks. Only the now-shared environment validator is removed from this task
source.

### Parameterized handwritten DSL

The Pilot 0.3 schema remains frozen:

```python
STAGES = [
    ("L1", "P1", 8, "R1", "Q1", 10),
]
```

No fields, special cases, or semantic capabilities were added. Base
configuration files are checked byte-for-byte against Pilot 0.3.

## Semantic validation

The shared test suite preserves branch assignments, exact deadlines, deadline
plus one, missing decisions, both branches, order violations, missing/wrong
goals, goals before choices, early `E`, goal reordering, and the `k=6` full
reversal failure. It also generates 10,000 deliberately mixed structured-random
traces for each `k=1,...,6`, using seed `20260901 + k`.

For every validated trace:

```text
Core TL          == oracle
expanded Macro TL == oracle
explicit monitor == oracle
parameterized DSL == oracle
```

The current run evaluates 61,219 traces per representation. All mismatch counts
are zero, and every Macro/Core AST equality field is `True`.

## Measurement definitions

No aggregate complexity score is created.

### Semantic payload

Each stage exposes six task-specific payload fields:

```text
Li, Pi, 8, Ri, Qi, 10
```

Thus the reported stage payload is `6k`. Fixed task-wide information—`S`, `E`,
and stage ordering—is documented separately. This is a transparent parameter
count, not an information-theoretic lower bound.

### Task-value occurrence count

The runner counts exact lexical occurrences of those six stage values in each
author-facing source. At `k` stages the canonical counts are:

```text
Core TL:           12k
Macro TL:           8k
Explicit monitor:   6k
Parameterized DSL:  6k
```

Macro TL repeats `Li/Ri` once in `ORDERED_CHOICES` and once in the corresponding
stage macro. This transparent repetition explains part of its residual size gap
from the parameterized DSL.

### Surface expansion ratio

For `k>=1`:

```text
author-facing tokens / (6k semantic payload fields)
```

This is called surface expansion, not complexity.

### Macro compression

```text
expanded Core-TL tokens / Macro-TL surface tokens
```

This measures syntax hidden by the reusable macro layer, not semantic
simplification.

### Structural edits

Canonical source edits use `SequenceMatcher(autojunk=False)`. Normalized ordered
tree edit uses APTED with unit insert/delete/rename costs. Tree distances are
only interpreted within the same representation. Cross-language tree-edit units
are not treated as equivalent.

## Modification audits

### Add one stage

For `B_k -> B_(k+1)`, the added semantic payload is exactly six fields. Macro TL
reports its surface edit and expanded Core-TL edit separately.

### Branch-local rewire

For `q=ceil(k/2)`, only `Pq -> Xq` changes on the left branch. Old-goal failure,
new-goal success, and unchanged right-branch behavior are independently checked.

### Macro-definition refactor

Definition V1 directly creates four Core-TL clauses. Definition V2 composes the
same result from `EXCLUSIVE_CHOICE` and `BOUNDED_RESPONSE` helpers. Task sources
remain byte-identical, and both versions expand to identical Core-TL ASTs.

The infrastructure implementation changes substantially, while every task
source edit and expanded semantic edit is zero. This demonstrates why language
implementation changes must be reported separately from task edits.

## Validated results

Author-facing lexical tokens are:

| k | Core TL | Macro TL | Explicit | Parameterized |
|---:|---:|---:|---:|---:|
| 0 | 6 | 11 | 51 | 4 |
| 1 | 95 | 30 | 152 | 18 |
| 2 | 184 | 50 | 255 | 32 |
| 3 | 273 | 70 | 358 | 46 |
| 4 | 362 | 90 | 461 | 60 |
| 5 | 451 | 110 | 566 | 74 |
| 6 | 540 | 130 | 669 | 88 |

The measured interpretation is:

- Core TL adds exactly 89 tokens per stage.
- Macro TL adds about 20 tokens per stage.
- The parameterized DSL adds 14 tokens per stage.
- The explicit monitor adds about 103 tokens per stage.
- At `k=6`, Macro TL compresses its 540-token Core expansion into 130 surface
  tokens, a compression ratio of about 4.15.
- The Core-TL/parameterized gap at `k=6` is 452 tokens; replacing primitive TL
  with Macro TL reduces the remaining gap to 42 tokens—about 91% of the previous
  gap is associated with the author-facing abstraction boundary in this setup.
- Macro TL is still larger than the frozen parameterized DSL: 130 versus 88
  tokens, and surface expansion 3.61 versus 2.44. Abstraction granularity does
  not explain the entire difference.
- Rewiring `Pq -> Xq` changes exactly one author-facing token and one normalized
  surface-tree node in all four representations.

The defensible conclusion is therefore:

> The large Core-TL/parameterized size gap in Pilot 0.3 is substantially
> attributable to abstraction granularity, but the chosen Macro-TL interface
> retains a smaller residual syntax/duplication gap from the parameterized DSL.

This does not establish that either language is easier to understand or
maintain.

## Infrastructure boundary

Macro syntax, parser, expander, formatter, and V1 definitions are reported as
the abstraction-introduction cost. Core-TL infrastructure already existed and
is reported separately. The V2 helper refactor is also reported separately so
it does not inflate the initial macro-layer cost.

The infrastructure plot is descriptive only. Its token counts are not treated
as a cross-language complexity comparison.

## Reproduce

From the repository root after installing `requirements.txt`:

```bash
cd pilots/pilot_0_3b_abstraction_audit
python -m pytest
python run_experiment.py
```

The experiment regenerates `generated/`, `results/`, and `plots/`
deterministically. Timestamps are intentionally excluded.

## Outputs

- `results/abstraction_summary.csv`: main author-facing comparison table.
- `results/construction.csv`: all raw construction and structural metrics.
- `results/semantics.csv`: oracle agreement and Macro/Core AST equality.
- `results/stage_add_edit.csv`: author-facing and Macro-expanded stage edits.
- `results/branch_rewire_edit.csv`: surface and expanded rewire edits.
- `results/macro_infrastructure_refactor.csv`: V1/V2 infrastructure audit.
- `results/baseline_fairness.csv`: machine-readable comparison boundary.
- `results/infrastructure.csv`: meaningful reusable components only.
- `results/metadata.json`: frozen assumptions, versions, seeds, and source hash.
- `results/checksums.sha256`: deterministic result-file hashes.
- `generated/B0` ... `generated/B6`: all surface sources, expansions, and trees.
- `plots/`: six separate descriptive plots; no overall complexity score.
