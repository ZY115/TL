#!/usr/bin/env python3
"""Freeze all arm trees before the coordinator releases held-out tasks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "freeze/freeze_manifest.json"
ARM_PATHS = {
    "a1_commit": ROOT / "arms/a1_ltlf",
    "a2a_commit": ROOT / "arms/a2_specialized_dsl/design_a",
    "a2b_commit": ROOT / "arms/a2_specialized_dsl/design_b",
    "a2c_commit": ROOT / "arms/a2_specialized_dsl/design_c",
    "a3_adapter_commit": ROOT / "arms/a3_handwritten/frozen_adapter",
}
DESIGN_SEED_TAGS = {"a2a": 1101, "a2b": 2202, "a2c": 3303}


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    if not files:
        raise AssertionError(f"Arm directory is empty: {directory}")
    for path in files:
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = {key: f"tree-sha256:{tree_hash(path)}" for key, path in ARM_PATHS.items()}
    already_frozen = all(
        str(manifest.get(key, "")).startswith("tree-sha256:") for key in ARM_PATHS
    )
    if already_frozen:
        if any(manifest[key] != value for key, value in current.items()):
            raise AssertionError("A frozen arm tree changed")
        print("All arm tree hashes remain frozen and unchanged.")
        return
    if any(manifest.get(key) != "pending_after_P0_gate" for key in ARM_PATHS):
        raise AssertionError("Partial or unrecognized arm freeze state")
    manifest.update(current)
    manifest["a2_design_seed_tags"] = DESIGN_SEED_TAGS
    manifest["arm_freeze_time"] = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest["heldout_release_status"] = "released to coordinator only after all arm tree hashes were frozen"
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("All arm trees frozen; held-out coordinator release gate is open.")


if __name__ == "__main__":
    main()
