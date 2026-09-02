#!/usr/bin/env python3
"""Two-stage adaptive trial plan with a seeded A2 design rotation.

Pilot 1.1 ran a fixed 10 × 5 × 10 grid because its author was so noisy that
per-cell rates needed many replicates. A capable author is nearly
deterministic on easy items, so replicates buy little there; tasks are the
informative dimension. The plan therefore:

* runs every released task against three arms — A1, one rotated A2 design,
  and A3 — with a single replicate in stage 1;
* adds ``STAGE2_EXTRA`` replicates per arm only on tasks whose stage-1 arm
  outcomes were not unanimous, where additional samples can change the
  verdict;
* fixes the A2 rotation by a seeded permutation written to
  ``freeze/stage_plan.json`` before any audit task is released.

    python -m author_harness.stage_plan freeze         # before release
    python -m author_harness.stage_plan stage1         # list stage-1 trials
    python -m author_harness.stage_plan stage2         # after stage-1 scoring
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "freeze/stage_plan.json"
DESIGNS = ("a2a", "a2b", "a2c")
ROTATION_SEED = 20_261_302
STAGE2_EXTRA = 2


def freeze_plan(task_ids: list[str]) -> dict[str, object]:
    if PLAN.exists():
        raise SystemExit(f"{PLAN} already exists; the rotation is frozen")
    rng = random.Random(ROTATION_SEED)
    order = list(DESIGNS)
    rng.shuffle(order)
    assignment = {
        task_id: order[index % len(order)] for index, task_id in enumerate(task_ids)
    }
    plan = {
        "rotation_seed": ROTATION_SEED,
        "stage2_extra_replicates": STAGE2_EXTRA,
        "a2_assignment": assignment,
        "arms_per_task": ["a1", "<assigned a2>", "a3"],
    }
    PLAN.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def load_plan() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def stage1_trials() -> list[tuple[str, str, int]]:
    plan = load_plan()
    trials = []
    for task_id, design in sorted(plan["a2_assignment"].items()):  # type: ignore[union-attr]
        for arm in ("a1", design, "a3"):
            trials.append((task_id, arm, 0))
    return trials


def stage2_trials(trials_csv: Path) -> list[tuple[str, str, int]]:
    """Tasks whose three stage-1 outcomes disagree get extra replicates."""
    plan = load_plan()
    extra = int(plan["stage2_extra_replicates"])
    with trials_csv.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["replicate"] == "0"]
    by_task: dict[str, set[bool]] = {}
    for row in rows:
        by_task.setdefault(row["task_id"], set()).add(row["first_attempt_correct"] == "True")
    trials = []
    for task_id, outcomes in sorted(by_task.items()):
        if len(outcomes) < 2:
            continue
        design = plan["a2_assignment"][task_id]  # type: ignore[index]
        for arm in ("a1", design, "a3"):
            for replicate in range(1, extra + 1):
                trials.append((task_id, arm, replicate))
    return trials


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "stage1", "stage2"))
    args = parser.parse_args()
    if args.command == "freeze":
        cards = sorted((ROOT / "released_audit/task_cards").glob("audit_*.txt"))
        gold = sorted((ROOT / "coordinator_private/gold_ir/audit").glob("audit_*.json"))
        task_ids = [path.stem for path in (cards or gold)]
        if not task_ids:
            raise SystemExit("no audit tasks to plan")
        plan = freeze_plan(task_ids)
        print(json.dumps(plan["a2_assignment"], indent=2))
        return
    trials = stage1_trials() if args.command == "stage1" else stage2_trials(
        ROOT / "results/trials.csv"
    )
    for task_id, arm, replicate in trials:
        print(f"{task_id}\t{arm}\t{replicate}")
    print(f"# {len(trials)} trials", flush=True)


if __name__ == "__main__":
    main()
