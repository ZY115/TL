# Pilot 1.0 — Held-Out Task Specification Benchmark

Pilot 1.0 supersedes source-size crossover as the active research methodology
while preserving all Pilot 0.1–0.4 code and outputs. It asks instead:

1. which exact task analyses are available from each representation's native
   semantic artifact, and what extra modeling they require;
2. how frozen representations adapt when held-out tasks introduce unseen
   semantic compositions.

Source size and edit distance remain secondary descriptive measurements. This
benchmark does not measure human comprehension or maintainability, does not run
RL, and does not study reactive synthesis against an adversarial environment.

## Current implementation status

The required build order is enforced:

| Phase | Status | Gate |
|---|---|---|
| P0 — environment, Neutral IR, two reference pipelines | **complete** | 750,000 dual-pipeline trace evaluations, zero mismatches |
| Freeze — A1, A2a/A2b/A2c, A3 adapter | **complete** | five arm-tree hashes recorded; held-out coordinator gate opened afterwards |
| Frozen-arm conformance | **complete** | 3,000,000 arm/oracle evaluations, zero mismatches |
| P1 — 60 analysis cases and 20 evolution streams | not started | held-out set is now released to the coordinator |
| P2 — cached author-modification study | not started | blocked by P1 artifacts and generation cache |

`python run_experiment.py` currently reproduces P0 and the frozen-arm gate. It
does not present those phases as a complete Pilot 1.0 result.

## P0 environment

All three JSON-compatible YAML maps define an 8×8 deterministic warehouse with
`UP`, `DOWN`, `LEFT`, `RIGHT`, `WAIT`, and terminating `STOP`. A movement into a
wall leaves the position unchanged. Every trace has at most `H=40` states.
`WAIT` permits padding and therefore interacts with deadlines.

`warehouse_blocked` and `warehouse_bottleneck` are tested to satisfy:

```text
B -> C is reachable
B -> C while avoiding X is unreachable
```

Thus every B-to-C path crosses X. This is a geometric infeasibility witness,
not merely a contradictory formula.

Only existential paths in a deterministic transition system are considered.
Every no-witness claim must be written as "no witness within H"; game-theoretic
realizability and reactive synthesis are out of scope.

## Neutral Task IR

The shared IR contains:

```text
Visit · Avoid · OrderedVisit · Deadline · MaintainUntil
On · Alternative · AllOf
CountAtMost · Once · Since · Threshold · Priority
```

IR names denote task semantics, not TL operators. `Threshold` reads explicit
resource channels (`battery`, `load`). `Once` and `Since` have past-time
semantics at their evaluation position. `Priority` is explicitly not treated
as an LTLf operator: Boolean acceptance means at least one ranked option is
satisfied, while the first satisfied rank is retained as a separate preference
answer.

Finite-trace next is strong: `X p` is false at the last position. A bounded
deadline expands as `X^l p | ... | X^u p`. Both facts, `H=40`, and the
1,000,000-state / 60-second automaton budgets are pinned in metadata.

## Two reference pipelines

- `neutral_ir/interpreter.py` evaluates the mathematical IR directly.
- `reference/automaton.py` contains a separately written evaluator behind the
  project's own bounded DFA interface; it never calls the direct interpreter.

For each of 15 training tasks, P0 uses 20,000 uniform-random traces, 15,000
constructively satisfying traces, and 15,000 targeted mutations. The current
gate contains 750,000 traces and zero cross-pipeline mismatches. This is a
conformance gate, not a scientific result. Two implementations can still share
the same misreading.

The bounded reference DFA stores exact trace-prefix states. It is sound and
complete below its explicit budget but is not a claim of an efficient mature
LTLf synthesis backend. Budget exhaustion is a first-class outcome; it is never
silently dropped.

## Frozen split

The deterministic split algorithm and the held-out payload were hashed before
representation design. Fifteen training tasks expose every primitive
individually. Twenty held-out streams contain ten cumulative additions each;
their novelty is composition only. Four atom/constant-only controls have
`unseen_composition_count=0` and are reported separately.

The primary structural variable is recomputed from the IR as:

```text
unseen edges and root-to-leaf type paths of length <= 3
relative to the complete training set
```

The full signature also records max nesting depth, node count, scope nesting,
and alternative arities. An isolated rater classified the ten neutrality-audit
samples as logic 4, configuration 3, and neutral/mixed 3, so the small audit
does not show a gross one-sided skew. This audit cannot prove neutrality.

The held-out payload was released to the coordinator only after the A1, three
A2, and A3-adapter tree hashes were written. The three A2 designers were
isolated and restricted to the training catalog, environment, and IR docs;
they did not inspect `benchmark/heldout`, `freeze`, the split algorithm,
results, or one another. Their fixed design seed tags are 1101, 2202, and 3303.

All three A2 designs are closed DSLs with deterministic task-source encoders.
They reject host-language execution mechanisms and retain every task ID,
requirement ID, bound, symbol, and nested structure in the counted source.
Their individual focused test suites contain 11, 9, and 8 passing tests.

After the freeze, A1 and A2a/A2b/A2c were evaluated against the direct IR
interpreter on exactly the same 50,000 traces for each training task. The
result is 3,000,000 arm evaluations with zero mismatches. This is still only a
conformance gate, not evidence that one representation is better.

## Important design tension discovered before P1

The specification requires every primitive—including counting, past-time,
resources, and priority—to appear individually in training. A genuinely
compositional A1 compiler may therefore learn all four extensions before the
freeze and compose them at held-out time without further infrastructure work.
This conflicts with the stated motivation that those primitives should force a
held-out A1 extension.

Pilot 1.0 will not manipulate A1 to create extensions artificially. If the
frozen A1 stack has zero held-out infrastructure changes, that outcome must be
reported together with its training-time extensions, task-source changes,
compile outcomes, and correctness. This tension limits what
"infrastructure-extension probability" alone can establish.

## Reproduce the completed gates

From the repository root:

```bash
source .venv/bin/activate
cd pilots/pilot_1_0_heldout_benchmark
pytest
python run_experiment.py
```

Key outputs are:

- `results/semantic_validation.csv` — the P0 conformance gate;
- `results/arm_conformance.csv` — A1 and all three A2 designs against the IR oracle;
- `results/environment_properties.csv` — geometric assertions;
- `results/structural_split.csv` — recomputable novelty metrics;
- `results/neutrality_audit.csv` — isolated classifications;
- `freeze/freeze_manifest.json` — sealed split and immutable arm-tree hashes;
- `results/metadata.json` and `checksums.sha256` — assumptions and provenance.

## Interpretation boundary

All future findings remain bounded to this 8×8 environment family, `H=40`, the
chosen IR, the sampled compositions, and the frozen designs. `unsupported`
will mean unsupported under a stated interface, never undecidable. No result
will be generalized to humans; the planned modification study uses cached LLM
generations and is explicitly a model-specific authoring study.
