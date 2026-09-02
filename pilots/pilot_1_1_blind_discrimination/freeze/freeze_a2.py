#!/usr/bin/env python3
"""Freeze the three blind A2 designs after coordinator conformance."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "freeze/freeze_manifest.json"
DESIGNS = {
    "a2a": (ROOT / "a2_designs/design_a", 11_101),
    "a2b": (ROOT / "a2_designs/design_b", 22_202),
    "a2c": (ROOT / "a2_designs/design_c", 33_303),
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    )
    if not files:
        raise AssertionError(f"empty frozen tree: {directory}")
    for path in files:
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_conformance() -> None:
    path = ROOT / "freeze/a2_training_conformance.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or sum(int(row["oracle_mismatches"]) for row in rows):
        raise AssertionError(
            "A2 designs cannot freeze before zero-mismatch conformance"
        )


def main() -> None:
    _assert_conformance()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current: dict[str, object] = {}
    for short_name, (directory, seed) in DESIGNS.items():
        current[f"{short_name}_tree_hash"] = tree_hash(directory)
        current[f"{short_name}_documentation_hash"] = file_hash(directory / "README.md")
        current[f"{short_name}_interpreter_hash"] = tree_hash(
            directory / "warehouse_dsl"
        )
        current[f"{short_name}_design_seed_tag"] = seed
    already_frozen = all(
        not str(manifest[f"{name}_tree_hash"]).startswith("pending") for name in DESIGNS
    )
    if already_frozen:
        for key, value in current.items():
            if manifest.get(key) != value:
                raise AssertionError(f"frozen A2 artifact changed: {key}")
        print("All A2 hashes remain frozen and unchanged.")
        return
    if any(manifest[f"{name}_tree_hash"] != "pending_blind_design" for name in DESIGNS):
        raise AssertionError("partial A2 freeze is forbidden")
    manifest.update(current)
    manifest["a2_freeze_time"] = (
        datetime.now().astimezone().isoformat(timespec="seconds")
    )
    manifest["audit_release_status"] = "sealed; A2 frozen; audit not yet curated"
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Three blind A2 designs frozen after zero-mismatch training conformance.")


if __name__ == "__main__":
    main()
