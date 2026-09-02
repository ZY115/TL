#!/usr/bin/env python3
"""Build and validate Pilot 1.0 P0 shared semantic backend."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
from dataclasses import fields
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("Pilot 1.0 requires Python 3.11 or newer")

from benchmark.generate_split import materialize
from benchmark.split_algorithm import control_tasks, heldout_streams, training_tasks
from environments.warehouse import Warehouse
from experiments.p0_calibration import HORIZON, TRACE_COUNT, validation_rows
from neutral_ir.schema import Expr, TaskSpec, task_from_dict
from neutral_ir.structure_signature import (
    children,
    signature_to_dict,
    structure_signature,
    unseen_composition_count,
)

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
FREEZE = ROOT / "freeze"
BASE_SEED = 20_261_100
FREEZE_TIME = "2026-09-01T16:39:39-0700"

SEMANTIC_COLUMNS = [
    "task_id",
    "trace_type",
    "num_trajectories",
    "direct_reference_matches",
    "direct_reference_mismatches",
    "satisfying_trajectories",
    "random_seed",
]
SPLIT_COLUMNS = [
    "item_id",
    "bucket",
    "unseen_composition_count",
    "unseen_parent_child_edges",
    "max_nesting_depth",
    "node_count",
    "scope_nesting_depth",
    "alternative_arities",
]
NEUTRALITY_COLUMNS = ["sample_id", "classification", "reason"]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _all_node_types(task: TaskSpec) -> set[str]:
    types: set[str] = set()

    def walk(expr: object) -> None:
        types.add(type(expr).__name__)
        for child in children(expr):  # type: ignore[arg-type]
            walk(child)

    for requirement in task.requirements:
        walk(requirement.expr)
    return types


def _assert_training_exposure() -> None:
    observed = set().union(*(_all_node_types(task) for task in training_tasks()))
    required = {
        "Visit",
        "Avoid",
        "OrderedVisit",
        "Deadline",
        "MaintainUntil",
        "On",
        "Alternative",
        "AllOf",
        "CountAtMost",
        "Once",
        "Since",
        "Threshold",
        "Priority",
    }
    if observed != required:
        raise AssertionError(
            f"Training primitive exposure differs: {observed ^ required}"
        )


def _assert_environment_geometry() -> list[dict[str, object]]:
    rows = []
    for path in sorted((ROOT / "environments").glob("warehouse_*.yaml")):
        warehouse = Warehouse.load(path)
        reachable = warehouse.path_exists("B", "C")
        avoiding = warehouse.path_exists("B", "C", forbidden_label="X")
        every_path_x = warehouse.every_path_uses("B", "C", "X")
        rows.append(
            {
                "environment": warehouse.name,
                "b_to_c_reachable": reachable,
                "b_to_c_avoiding_x_reachable": avoiding,
                "every_b_to_c_path_uses_x": every_path_x,
            }
        )
    if not any(row["every_b_to_c_path_uses_x"] for row in rows):
        raise AssertionError("No map makes B->C feasible only through X")
    return rows


def _split_rows() -> list[dict[str, object]]:
    training = training_tasks()
    train_edges = set().union(
        *(set(structure_signature(task).edges) for task in training)
    )
    rows = []
    for stream in heldout_streams():
        for state in stream["states"]:  # type: ignore[index]
            task = task_from_dict(state)
            signature = structure_signature(task)
            rows.append(
                {
                    "item_id": task.id,
                    "bucket": "compositional_heldout",
                    "unseen_composition_count": unseen_composition_count(
                        task, training
                    ),
                    "unseen_parent_child_edges": len(
                        set(signature.edges) - train_edges
                    ),
                    "max_nesting_depth": signature.max_nesting_depth,
                    "node_count": signature.node_count,
                    "scope_nesting_depth": signature.scope_nesting_depth,
                    "alternative_arities": "|".join(
                        map(str, signature.alternative_arities)
                    ),
                }
            )
    for task in control_tasks():
        signature = structure_signature(task)
        unseen = unseen_composition_count(task, training)
        if unseen != 0:
            raise AssertionError(f"Trivial control is structurally novel: {task.id}")
        rows.append(
            {
                "item_id": task.id,
                "bucket": "trivial_atom_or_constant_change",
                "unseen_composition_count": unseen,
                "unseen_parent_child_edges": len(set(signature.edges) - train_edges),
                "max_nesting_depth": signature.max_nesting_depth,
                "node_count": signature.node_count,
                "scope_nesting_depth": signature.scope_nesting_depth,
                "alternative_arities": "|".join(
                    map(str, signature.alternative_arities)
                ),
            }
        )
    compositional = [row for row in rows if row["bucket"] == "compositional_heldout"]
    if not any(int(row["unseen_composition_count"]) > 0 for row in compositional):
        raise AssertionError("Held-out set contains no recomputable structural novelty")
    return rows


def _freeze_manifest() -> dict[str, object]:
    train = ROOT / "benchmark/train/catalog.json"
    heldout = ROOT / "benchmark/heldout/sealed_streams.json"
    controls = ROOT / "benchmark/heldout/trivial_controls.json"
    manifest = {
        "train_hash": _sha256_file(train),
        "heldout_hash": _sha256_bytes(heldout.read_bytes() + controls.read_bytes()),
        "split_algo_hash": _sha256_file(ROOT / "benchmark/split_algorithm.py"),
        "a1_commit": "pending_after_P0_gate",
        "a2a_commit": "pending_after_P0_gate",
        "a2b_commit": "pending_after_P0_gate",
        "a2c_commit": "pending_after_P0_gate",
        "a3_adapter_commit": "pending_after_P0_gate",
        "freeze_time": FREEZE_TIME,
        "heldout_release_status": "sealed; not released to representation designers",
    }
    path = FREEZE / "freeze_manifest.json"
    canonical = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        for key in (
            "train_hash",
            "heldout_hash",
            "split_algo_hash",
            "freeze_time",
        ):
            if existing.get(key) != manifest[key]:
                raise AssertionError(f"Freeze manifest drifted after sealing: {key}")
        return existing
    path.write_text(canonical, encoding="utf-8")
    return manifest


def _neutrality_rows() -> list[dict[str, object]]:
    path = FREEZE / "neutrality_audit.csv"
    if not path.exists():
        raise RuntimeError(
            "Neutrality audit is missing. An isolated rater must classify freeze/neutrality_sample.json before the P0 gate can pass."
        )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sample = json.loads((FREEZE / "neutrality_sample.json").read_text(encoding="utf-8"))
    if {row["sample_id"] for row in rows} != {item["sample_id"] for item in sample}:
        raise AssertionError(
            "Neutrality audit sample IDs do not match the sealed sample"
        )
    allowed = {"logic", "configuration", "neutral/mixed"}
    if any(row["classification"] not in allowed for row in rows):
        raise AssertionError("Unknown neutrality classification")
    return rows


def _checksums() -> None:
    files = []
    for directory in (
        ROOT / "environments",
        ROOT / "neutral_ir",
        ROOT / "reference",
        ROOT / "benchmark",
        ROOT / "freeze",
        RESULTS,
    ):
        files.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.name != "checksums.sha256"
        )
    lines = [
        f"{_sha256_file(path)}  {path.relative_to(ROOT)}" for path in sorted(set(files))
    ]
    (RESULTS / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    materialize(ROOT / "benchmark")
    _assert_training_exposure()
    environment_rows = _assert_environment_geometry()
    split_rows = _split_rows()
    manifest = _freeze_manifest()
    neutrality = _neutrality_rows()

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    RESULTS.mkdir(parents=True)
    semantic_rows = []
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    for index, task in enumerate(training_tasks()):
        semantic_rows.extend(validation_rows(task, warehouse, seed=BASE_SEED + index))
    mismatches = sum(int(row["direct_reference_mismatches"]) for row in semantic_rows)
    if mismatches:
        raise AssertionError(
            "P0 semantic conformance failed; no comparison metric may be exported"
        )

    _write_csv(RESULTS / "semantic_validation.csv", SEMANTIC_COLUMNS, semantic_rows)
    _write_csv(RESULTS / "structural_split.csv", SPLIT_COLUMNS, split_rows)
    _write_csv(
        RESULTS / "environment_properties.csv",
        [
            "environment",
            "b_to_c_reachable",
            "b_to_c_avoiding_x_reachable",
            "every_b_to_c_path_uses_x",
        ],
        environment_rows,
    )
    _write_csv(RESULTS / "neutrality_audit.csv", NEUTRALITY_COLUMNS, neutrality)
    neutrality_counts = {
        label: sum(row["classification"] == label for row in neutrality)
        for label in ("logic", "configuration", "neutral/mixed")
    }
    metadata = {
        "pilot": "1.0",
        "phase": "P0_shared_backend",
        "phase_status": "complete",
        "full_pilot_status": "P1/P2 not started; representation arms remain frozen-pending",
        "supersedes": "tl_sequence_pilot 0.1-0.4 as the active methodology; old outputs are preserved",
        "horizon": HORIZON,
        "wait_allows_padding": True,
        "environment_question": "existential path in deterministic transition system",
        "reactive_synthesis_out_of_scope": True,
        "finite_trace_next": "strong X; false at the final position",
        "bounded_expansion": "F[l,u] p = X^l p OR ... OR X^u p",
        "dfa_state_budget": 1_000_000,
        "dfa_timeout_seconds": 60,
        "training_task_count": len(training_tasks()),
        "heldout_stream_count": len(heldout_streams()),
        "steps_per_heldout_stream": 10,
        "traces_per_training_task": TRACE_COUNT,
        "trace_mixture": {
            "uniform_random": 0.4,
            "constructive_satisfying": 0.3,
            "targeted_mutation": 0.3,
        },
        "semantic_gate_mismatches": mismatches,
        "neutrality_audit_counts": neutrality_counts,
        "priority_boolean_semantics": "accept iff at least one ranked option is satisfied; preferred satisfied rank is retained separately and is not an LTLf trace operator",
        "split_seed": 20_261_001,
        "calibration_seed_base": BASE_SEED,
        "freeze_manifest_hash": _sha256_bytes(
            json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
        ),
        "python": platform.python_version(),
        "packages": {
            package: importlib.metadata.version(package)
            for package in ("black", "matplotlib", "pandas", "pytest")
        },
        "known_limitations": [
            "The bounded prefix DFA is exact but may hit its explicit 1e6-state/60s synthesis budget.",
            "Two independently implemented semantic pipelines can still share a misreading.",
            "P0 validates reference semantics only; arm conformance is gated until P1 artifacts exist.",
        ],
    }
    (RESULTS / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _checksums()
    print(
        f"Pilot 1.0 P0 complete: {sum(int(row['num_trajectories']) for row in semantic_rows):,} dual-pipeline evaluations, zero mismatches."
    )


if __name__ == "__main__":
    main()
