# Temporal Logic vs. Handwritten Monitor — Pilot Suite

This repository contains a sequence of reproducible methodology-calibration
experiments. Each pilot compares three first-class task representations:

1. a finite-trace temporal-logic specification;
2. a canonical explicit handwritten monitor;
3. a reasonable parameterized handwritten monitor.

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
    └── pilot_0_3_branch_timing/
```

| Pilot | Independent variable | Fixed structure | Main modification |
|---|---|---|---|
| [0.1 — Sequence](pilots/pilot_0_1_sequence/README.md) | ordered-sequence length `n=1...10` | sequence-only semantics | insert one target `X` |
| [0.2 — Timing](pilots/pilot_0_2_timing/README.md) | overlapping deadlines `m=0...5` | ten-event sequence | add a constraint; change `8 -> 6` |
| [0.3 — Branch + timing](pilots/pilot_0_3_branch_timing/README.md) | conditional stages `k=0...6` | left/right bounded obligations | add a stage; rewire `Pq -> Xq` |

Every pilot owns its `src/`, `tests/`, `generated/`, `results/`, and `plots/`
directories. This prevents later experiments from overwriting earlier outputs.

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
cd pilots/pilot_0_3_branch_timing
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

Do not combine AST or tree-edit units from different representation languages
into a synthetic overall-complexity score. Those metrics are primarily for
within-representation growth and before/after comparisons.
