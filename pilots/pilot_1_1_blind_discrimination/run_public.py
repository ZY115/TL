#!/usr/bin/env python3
"""Public verification. Never opens gold trees, hidden traces, or the oracle.

Checks that the published record is internally consistent:

* the public training corpus matches its frozen hash;
* every frozen representation still hashes to its manifest value;
* the audit was released only after the complete freeze;
* every cached candidate's stored artifact hash matches its bytes;
* published result files match ``results/checksums.sha256``.

A reader without the coordinator bundle can run this and confirm that no
measured artifact or frozen representation changed after release.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED_TRIALS = 500
RESULT_FILES = (
    "trials.csv",
    "task_summary.csv",
    "arm_summary.csv",
    "failure_modes.csv",
    "ambiguity_audit.csv",
    "discrimination_gate.json",
    "metadata.json",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _tree_hash(directory: Path) -> str:
    """Byte-identical to the convention used by the freeze scripts."""
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


def _bundle_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    manifest = json.loads(
        (ROOT / "freeze/freeze_manifest.json").read_text(encoding="utf-8")
    )
    failures: list[str] = []
    checks = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(f"{label}{': ' + detail if detail else ''}")

    training = _tree_hash(ROOT / "public/training_tasks")
    check(
        "training corpus hash",
        training == manifest["training_task_hash"],
        f"{training} != {manifest['training_task_hash']}",
    )
    check(
        "A1 reference hash",
        _sha256_file(ROOT / "public/a1_ltlf_reference.md")
        == manifest["a1_reference_hash"],
    )
    check(
        "A1 language tree hash",
        _tree_hash(ROOT / "a1_ltlf") == manifest["a1_language_tree_hash"],
    )
    check(
        "A3 API hash",
        _sha256_file(ROOT / "public/a3_monitor_api.md") == manifest["a3_api_hash"],
    )
    for key, design in (("a2a", "design_a"), ("a2b", "design_b"), ("a2c", "design_c")):
        base = ROOT / "a2_designs" / design
        check(
            f"{key} interpreter hash",
            _tree_hash(base / "warehouse_dsl")
            == manifest[f"{key}_interpreter_hash"],
        )
        check(
            f"{key} tree hash",
            _tree_hash(base) == manifest[f"{key}_tree_hash"],
        )
        check(
            f"{key} documentation hash",
            _sha256_file(base / "README.md") == manifest[f"{key}_documentation_hash"],
        )

    check(
        "audit released only after complete freeze",
        manifest["audit_release_status"] == "released_after_complete_freeze",
        manifest["audit_release_status"],
    )
    for key in ("gold_audit_bundle_hash", "hidden_test_bundle_hash"):
        check(f"{key} recorded", not str(manifest[key]).startswith("pending"))

    cards = sorted((ROOT / "released_audit/task_cards").glob("audit_*.txt"))
    check("ten released cards", len(cards) == 10, str(len(cards)))
    check(
        "released card bundle hash",
        _bundle_hash(cards) == manifest.get("released_card_bundle_hash"),
    )

    isolation = json.loads(
        (ROOT / "freeze/isolation_check.json").read_text(encoding="utf-8")
    )
    check("isolation sentinel", isolation["isolation_check"] == "passed")
    check(
        "sentinel absent from every author environment",
        all(
            item["sentinel_absent_from_prompt"] and item["sentinel_absent_from_response"]
            for item in isolation["author_environments"]
        ),
    )

    trial_dirs = sorted(
        path
        for path in (ROOT / "candidate_cache").iterdir()
        if path.is_dir() and (path / "metadata.json").exists()
    )
    check("cached trial count", len(trial_dirs) == EXPECTED_TRIALS, str(len(trial_dirs)))
    drifted = []
    for trial_dir in trial_dirs:
        meta = json.loads((trial_dir / "metadata.json").read_text(encoding="utf-8"))
        artifact = (trial_dir / "artifact.txt").read_text(encoding="utf-8")
        response = (trial_dir / "raw_response.txt").read_text(encoding="utf-8")
        if _sha256_text(artifact) != meta["artifact_hash"]:
            drifted.append(f"{trial_dir.name} artifact")
        if _sha256_text(response) != meta["response_hash"]:
            drifted.append(f"{trial_dir.name} response")
        if meta["model"] != manifest["model_configuration"]["model"]:
            drifted.append(f"{trial_dir.name} model")
    check("cached artifact and response hashes", not drifted, "; ".join(drifted[:5]))

    checksums = ROOT / "results/checksums.sha256"
    if checksums.exists():
        recorded = dict(
            reversed(line.split("  ", 1)) for line in checksums.read_text().splitlines()
        )
        for name in RESULT_FILES:
            path = ROOT / "results" / name
            check(f"result file present: {name}", path.exists())
            if path.exists():
                check(
                    f"result checksum: {name}",
                    recorded.get(name) == _sha256_file(path),
                )
    else:
        check("results/checksums.sha256 present", False, "audit not yet summarized")

    print(f"public verification: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("\nFAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("Public record is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
