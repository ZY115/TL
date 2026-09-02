# Pilot 1.1 — Blind Representation Discrimination Audit

Pilot 1.1 validates the benchmark apparatus before any large-scale
representation study. Its primary outcome is **first-attempt hidden-suite
correctness** when standard LTLf, three independently designed task DSLs, and
handwritten Python are all authored from the same natural-language task card.

This pilot does not study source-size crossover, infrastructure evolution,
analysis readiness, human maintainability, RL, or expressiveness outside the
fixed future-time fragment. It does not assume that LTLf will win.

## Status — audit iteration 1 complete

| Stage | Status |
|---|---|
| Preserve Pilot 1.0 | complete; pre-build tree hash recorded |
| Coordinator/public boundary | complete |
| Fixed standard-LTLf A1 | complete |
| Fresh natural-language training corpus | complete; 14 cards |
| Three blind A2 designs | complete; frozen, zero training mismatches |
| Ambiguity audit | complete; 10/10 released |
| Ten sacrificial audit tasks | released after complete freeze |
| 500 first-attempt generations | complete; cached |
| Hidden evaluation and discrimination gate | complete |

**Gate verdict: `passes_gate = false`, floor failure on 9 of 10 tasks.**
Do not scale this configuration into the full benchmark.

## Headline result

| Arm | Trials | Parse success | Runtime success | First-attempt correct |
|---|---:|---:|---:|---:|
| A1 standard LTLf | 100 | 21% | 21% | **0%** |
| A2a windowed S-expression DSL | 100 | 2% | 2% | 1% |
| A2b block DSL | 100 | 9% | 9% | 9% |
| A2c call-syntax DSL | 100 | 2% | 2% | 2% |
| A2 pooled | 300 | 4.3% | 4.3% | 4% |
| A3 handwritten Python | 100 | 90% | 48% | 5% |

Only 2 of the required 3 tasks were discriminative. One systematic mode
separated the arms: A3 produced runtime errors in 44% of its failures while
A1 and A2 produced none, because those two fail earlier, at parse time.

## The floor is the author, not the tasks

The mechanical gate recommends `reduce_difficulty`. That action is not
available and must not be taken. The three low-novelty controls are

```text
audit_01  Visit A at least once before the finite trace ends.
audit_02  Never enter X anywhere in the finite trace.
audit_03  Visit A and then visit B at a strictly later step.
```

and mean correctness on them was A1 0%, A2 13%, A3 17%. A benchmark whose
easiest task is "visit A at least once" cannot be made easier. The binding
constraint is the frozen authoring model, `llama3.2:3b`, which never once
produced a syntactically valid **and** semantically correct LTLf formula in
100 attempts; 79% of its failures were syntax errors before any semantics
were reached.

`results/discrimination_gate.json` records this under
`author_capability_floor` so the floor verdict is not misread as a statement
about task difficulty.

## Capable-author probe — the floor was entirely the author

A follow-up probe changed **only** the author and held every frozen part of
the apparatus identical: same released cards, same exported prompts, same
hidden suites, same gold. Each artifact was written by a separate memoryless
agent that received exactly one exported prompt and no repository access.

The probe used `audit_09`, the hardest released task and the only one with
any structural novelty (`unseen_composition_count = 13`).

| Arm | Parse | Mismatches / 4,500 | First-attempt correct |
|---|---|---:|---|
| A1 standard LTLf | yes | 0 | yes |
| A2a | yes | 0 | yes |
| A2b | yes | 0 | yes |
| A2c | yes | 0 | yes |
| A3 handwritten Python | yes | 0 | yes |

**5/5, first attempt, zero mismatches.** See
`results/capable_author_probe.csv`; regenerate with
`python -m coordinator_private.capable_author_probe <artifact_dir>` and export
the prompts with `python -m author_harness.export_prompt <task_id> <arm>`.

This settles the floor question and replaces it with the opposite one. The
released tasks are not too hard — for a capable author they are close to
trivial. A full re-run would very likely trip the **ceiling** gate (§35) and
recommend `increase_neutral_compositional_difficulty`.

The probe is not an audit. Its rows never enter `trials.csv`, never feed the
discrimination gate, and do not consume a protocol iteration.

## What the audit did validate

The apparatus itself worked end to end:

- the information boundary held — the isolation sentinel never appeared in any
  prompt or response across all five author environments;
- the ambiguity audit caught a real conflict before release (two curator cards
  demanded a *strictly later* until-goal while the already-public
  `warehouse.md` contract admits the goal at the trigger step; both cards were
  repaired to the contract before any author saw them);
- gold semantics and compiled standard LTLf agreed on 29,331 traces per task,
  zero mismatches, satisfying the §31 expressibility precondition;
- all 10 hidden suites are exactly 4,500 traces, and every declared positive
  and targeted-negative template was re-verified against the gold oracle
  under every padding offset;
- 500 artifacts were cached with model, seed, and prompt hashes, and
  `run_public.py` re-verifies every artifact hash without opening gold.

## What the audit exposed about the benchmark design

Two defects surfaced that are independent of the model choice.

**1. The gold IR cannot express nested bounded continuations.** `Within` binds
a bare label, so the schema cannot say *choose the witness inside a bounded
window, then impose a further obligation measured from that witness*. Three of
six high-difficulty curator candidates (`high_01`, `high_04`, `high_06`) need
exactly that shape and were unannotatable. Two were formally excluded under
the precommitted replacement rule; see
`coordinator_private/candidate_pool/selection_outcome.json`. The exclusion is
representation-neutral — the same shape defeats all three frozen A2 grammars
too, and only A1 could express it — but it removed precisely the deepest
compositions.

This is now the binding defect. A weak author floors on these tasks and a
capable one ceilings; the tasks that would sit between those extremes are
exactly the ones the gold schema could not express.

**2. The compositional-novelty axis is degenerate.** After those exclusions,
9 of 10 released tasks have `unseen_composition_count = 0` and only `audit_09`
has any structural novelty at all. The training corpus nests only through
`Triggered`, and encodes multi-clause tasks as several top-level requirements
rather than as an `AllOf` node, so the released "high" tasks differ from
training in clause count and nesting depth but introduce no new parent-child
relationship. **This audit therefore could not test compositional
out-of-distribution generalization**, which was one of its stated purposes.

Fixing (1) is a precondition for fixing (2). Both belong to Pilot 1.2.

## Iteration accounting

Protocol §40 allows at most two benchmark-development audit iterations, and
every audit task ever used is permanently excluded from the final benchmark.
This run consumed **iteration 1** and burned tasks `audit_01`–`audit_10`
(curator candidates `low_01`–`low_03`, `medium_01`–`medium_04`, `high_02`,
`high_03`, `high_05`). The remaining curator pool holds `low_04`–`low_06`,
`medium_05`, `medium_06`, and the three inexpressible high candidates.

Whether an iteration that floored for author incapacity should count against
that budget is a research-supervision decision, not an engineering one. The
conservative protocol default is applied here: it counts.

## Information boundary

Authors receive only copied files under an isolated `author_views/<trial>/`
directory. They never receive Neutral IR code, gold task structures, hidden
traces, structural novelty metadata, other representations, future tasks, or
the Pilot 1.0 A2 implementations. Author views contain no symlinks.

`coordinator_private/` is ignored during the blind phase. Only its
cryptographic bundle hashes enter `freeze/freeze_manifest.json`. Now that the
sacrificial audit is complete, the private bundle may be archived so that
coordinator-side regeneration is reproducible.

## Fixed semantics

Traces are finite sequences of proposition sets. LTLf next (`X`) is strong and
therefore false at the final position. A bounded future window is expressed
only as the standard expansion `X^l p | ... | X^u p`; there is no custom
bounded operator in A1. The scoped statement "avoid X until C" requires a `C`
at the current or a later step, forbids `X` strictly before the chosen `C`,
and allows `X` at the endpoint. When nested under a trigger, evaluation begins
at the trigger step.

## Reproduction

```bash
python run_public.py        # no gold, no hidden traces
python run_coordinator.py   # regenerates gold, suites, evaluation, gate
```

`run_coordinator.py` deliberately does not regenerate the 500 candidate
artifacts. Those cached responses are the measured data. Use
`python -m author_harness.generate --execute` to fill missing trials.

## Result files

| File | Contents |
|---|---|
| `results/ambiguity_audit.csv` | pre-release audit, per task |
| `results/trials.csv` | 500 rows, one per artifact |
| `results/task_summary.csv` | per-task arm rates and novelty metadata |
| `results/arm_summary.csv` | per-arm and pooled-A2 rates |
| `results/failure_modes.csv` | failure taxonomy by arm class |
| `results/failure_modes_by_task.csv` | same, split by task |
| `results/discrimination_gate.json` | ceiling, floor, discrimination, action |
| `results/capable_author_probe.csv` | capable-author probe; not part of the audit |
| `results/metadata.json` | model config, freeze hashes, thresholds |
| `results/checksums.sha256` | digests of every published result file |

Source size is recorded nowhere in these files and is not evidence. No
crossover claim is made or computed.
