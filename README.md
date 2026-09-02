# Temporal Logic vs. Handwritten Monitor — Pilot Suite

This repository contains a sequence of reproducible methodology-calibration
experiments. The core pilots compare three first-class task representations:

1. a finite-trace temporal-logic specification;
2. a canonical explicit handwritten monitor;
3. a reasonable parameterized handwritten monitor.

Pilot 0.3B adds a fourth Macro-TL representation to audit whether differences
come from the language or from the author-facing abstraction level. Pilot 0.4
then freezes an existing general TL stack and specialized DSL and measures how
their task sources and infrastructure evolve under cumulative heterogeneous
requirements.

The suite does **not** assume that temporal logic wins. It reports raw
task-specific representation size and structural edit footprint, validates all
implementations against independent semantic oracles, and keeps reusable
infrastructure separate.

## Repository structure

```text
tl_sequence_pilot/
├── README.md
├── requirements.txt
├── run_all.py
└── pilots/
    ├── pilot_0_1_sequence/
    ├── pilot_0_2_timing/
    ├── pilot_0_3_branch_timing/
    ├── pilot_0_3b_abstraction_audit/
    ├── pilot_0_4_frozen_evolution/
    ├── pilot_1_0_heldout_benchmark/
    ├── pilot_1_1_blind_discrimination/
    ├── pilot_1_2_compositional_audit/
    └── pilot_2_0_analysis_readiness/
```

| Pilot | Independent variable | Fixed structure | Main modification |
|---|---|---|---|
| [0.1 — Sequence](pilots/pilot_0_1_sequence/README.md) | ordered-sequence length `n=1...10` | sequence-only semantics | insert one target `X` |
| [0.2 — Timing](pilots/pilot_0_2_timing/README.md) | overlapping deadlines `m=0...5` | ten-event sequence | add a constraint; change `8 -> 6` |
| [0.3 — Branch + timing](pilots/pilot_0_3_branch_timing/README.md) | conditional stages `k=0...6` | left/right bounded obligations | add a stage; rewire `Pq -> Xq` |
| [0.3B — Abstraction audit](pilots/pilot_0_3b_abstraction_audit/README.md) | abstraction interface | exact Pilot 0.3 task family | compare Core TL, Macro TL, explicit, and parameterized surfaces |
| [0.4 — Frozen evolution](pilots/pilot_0_4_frozen_evolution/README.md) | cumulative requirement type `E0...E6` | fixed `B4` | separate task-source, infrastructure, validation, and migration evolution |
| [1.0 — Held-out benchmark](pilots/pilot_1_0_heldout_benchmark/README.md) | unseen semantic composition | fixed 8×8 warehouse family and `H=40` | analysis readiness and frozen-representation adaptation; P0 + arm freeze complete |
| [1.1 — Blind discrimination audit](pilots/pilot_1_1_blind_discrimination/README.md) | representation, authored blind from natural language | ten sacrificial audit tasks, one fixed authoring model | first-attempt hidden-suite correctness; **gate failed (floor), do not scale** |
| [1.2 — Compositional audit](pilots/pilot_1_2_compositional_audit/README.md) | representation, authored blind by memoryless Haiku agents | twelve realistic tasks, compositional gold IR, symmetric worked examples, two-stage adaptive plan | first-attempt hidden-suite correctness; **gate passed on spread (A1 20/20, A2 17/20, A3 16/20); paired test underpowered at n=12** |
| [2.0 — Analysis readiness](pilots/pilot_2_0_analysis_readiness/README.md) | representation, analysed as an artifact | 30 cases (12 released + 18 constructed), 8 questions, blocked floor plan | which questions each representation can answer, exactly or only by bounded search; **no authors, no agents, pure code** |

Every pilot owns its `src/`, `tests/`, `generated/`, `results/`, and `plots/`
directories. This prevents later experiments from overwriting earlier outputs.

Pilot 1.1 is a benchmark-validation experiment rather than a representation
study. It asks whether a genuinely blind apparatus can separate standard
LTLf, three independently designed DSLs, and free handwritten Python when all
are authored from the same natural-language cards. It publishes
`run_public.py` instead of `run_experiment.py`: its measured data are 500
cached model responses, so re-running the authoring stage would replace the
observations rather than reproduce them. Its first iteration floored — the
fixed 3B authoring model could not produce valid artifacts even for the
trivial control tasks — so its verdict is about the apparatus, not about any
representation.

## Environment

All pilots currently use the same pinned packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 or newer is required. The validated local environment used Python
3.12.13.

## Run one pilot

Each pilot remains independently reproducible with one experiment command:

```bash
cd pilots/pilot_0_3b_abstraction_audit
python run_experiment.py
```

Run its tests from the same directory:

```bash
pytest
```

## Run the complete suite

From the repository root:

```bash
python run_all.py
```

This runs each pilot's tests and experiment in order. A failure stops the suite.
Because every runner writes only inside its own pilot directory, outputs remain
separated.

## Reading the results

Within each pilot, the most useful files for sharing are:

- `README.md` for semantics, methodology, and interpretation;
- `results/semantics.csv` to establish zero oracle mismatches;
- `results/construction.csv` for raw construction measurements;
- the modification CSV files for structural edit footprint;
- `plots/` for presentation-ready visual summaries;
- `results/metadata.json` and `checksums.sha256` for reproducibility.

Pilot 0.4 uses different result names because its experimental unit is system
evolution rather than task-family construction. Start with
`results/evolution_steps.csv`, `results/cumulative.csv`,
`results/compatibility.csv`, and `results/semantics.csv`.

Pilot 1.0 supersedes size crossover as the active methodology but is built in
gated phases. Its current one-command entry point reproduces the completed P0
backend and frozen-arm semantic gate; it does not claim that the full Pilot 1.0
analysis/evolution/modification study is finished.

Do not combine AST or tree-edit units from different representation languages
into a synthetic overall-complexity score. Those metrics are primarily for
within-representation growth and before/after comparisons.
