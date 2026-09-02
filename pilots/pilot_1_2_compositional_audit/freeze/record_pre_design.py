#!/usr/bin/env python3
"""Freeze the standard A1 language and public training view before A2 design.

Pilot 1.2 preserves Pilot 1.1 byte-for-byte; its tree hash is recorded here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = ROOT.parent / "pilot_1_1_blind_discrimination"
MANIFEST = ROOT / "freeze/freeze_manifest.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        item
        for item in directory.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and ".pytest_cache" not in item.parts
    ):
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    values: dict[str, object] = {
        "pilot_1_1_preservation_hash": tree_hash(PREDECESSOR),
        "training_task_hash": tree_hash(ROOT / "public/training_tasks"),
        "a1_language_tree_hash": tree_hash(ROOT / "a1_ltlf"),
        "a1_reference_hash": file_hash(ROOT / "public/a1_ltlf_reference.md"),
        "a3_api_hash": file_hash(ROOT / "public/a3_monitor_api.md"),
        "a2a_tree_hash": "pending_blind_design",
        "a2b_tree_hash": "pending_blind_design",
        "a2c_tree_hash": "pending_blind_design",
        "gold_audit_bundle_hash": "pending_private_curation",
        "hidden_test_bundle_hash": "pending_private_curation",
        "author_prompt_hash": "pending_harness",
        "model_configuration": "pending_fixed_provider",
        "audit_release_status": "sealed; no audit task released",
        "pre_design_freeze_time": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
    }
    if MANIFEST.exists():
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for key in (
            "pilot_1_1_preservation_hash",
            "training_task_hash",
            "a1_language_tree_hash",
            "a1_reference_hash",
            "a3_api_hash",
        ):
            if existing.get(key) != values[key]:
                raise AssertionError(f"pre-design frozen artifact changed: {key}")
        print("Pre-design hashes remain frozen and unchanged.")
        return
    MANIFEST.write_text(
        json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Standard A1, training cards, A3 API, and Pilot 1.1 snapshot frozen.")


if __name__ == "__main__":
    main()
