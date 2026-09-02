#!/usr/bin/env python3
"""Freeze representation arms and run the pre-held-out conformance gate."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from benchmark.split_algorithm import training_tasks
from environments.warehouse import Warehouse
from experiments.arm_conformance import conformance_rows

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
BASE_SEED = 20_261_100
COLUMNS = [
    "task_id",
    "arm",
    "trace_type",
    "num_trajectories",
    "oracle_matches",
    "oracle_mismatches",
    "random_seed",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_checksums() -> None:
    files: list[Path] = []
    for directory in (
        ROOT / "environments",
        ROOT / "neutral_ir",
        ROOT / "reference",
        ROOT / "benchmark",
        ROOT / "freeze",
        ROOT / "arms",
        RESULTS,
    ):
        files.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
            and path.name != "checksums.sha256"
        )
    lines = [
        f"{_sha256(path)}  {path.relative_to(ROOT)}" for path in sorted(set(files))
    ]
    (RESULTS / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "freeze/freeze_arms.py")], check=True)
    manifest = json.loads(
        (ROOT / "freeze/freeze_manifest.json").read_text(encoding="utf-8")
    )
    if not all(
        str(manifest[key]).startswith("tree-sha256:")
        for key in (
            "a1_commit",
            "a2a_commit",
            "a2b_commit",
            "a2c_commit",
            "a3_adapter_commit",
        )
    ):
        raise AssertionError("Arm conformance cannot run before the arm freeze")

    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    rows: list[dict[str, object]] = []
    for index, task in enumerate(training_tasks()):
        rows.extend(conformance_rows(task, warehouse, seed=BASE_SEED + index))
    mismatches = sum(int(row["oracle_mismatches"]) for row in rows)
    if mismatches:
        raise AssertionError(
            f"Frozen-arm semantic conformance failed with {mismatches} mismatches"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "arm_conformance.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    metadata_path = RESULTS / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "arm_freeze_status": "complete",
            "arm_conformance_status": "passed",
            "arm_conformance_mismatches": 0,
            "arm_conformance_evaluations": sum(
                int(row["num_trajectories"]) for row in rows
            ),
            "freeze_manifest_hash": hashlib.sha256(
                (ROOT / "freeze/freeze_manifest.json").read_bytes()
            ).hexdigest(),
            "full_pilot_status": "P0 and frozen-arm gate complete; P1/P2 not started",
        }
    )
    metadata["known_limitations"] = [
        item
        for item in metadata["known_limitations"]
        if not str(item).startswith("P0 validates reference semantics only")
    ]
    metadata["known_limitations"].append(
        "Frozen-arm conformance covers the training suite; held-out authoring and analysis remain unmeasured until P1."
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _rewrite_checksums()
    print(
        "Pilot 1.0 frozen-arm gate complete: "
        f"{metadata['arm_conformance_evaluations']:,} evaluations, zero mismatches."
    )


if __name__ == "__main__":
    main()
