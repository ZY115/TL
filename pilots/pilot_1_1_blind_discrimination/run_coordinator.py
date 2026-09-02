#!/usr/bin/env python3
"""Coordinator-side regeneration of the whole hidden evaluation.

Runs the private stages in dependency order:

    gold annotation -> ambiguity audit -> hidden suites -> structural
    signatures -> release -> candidate evaluation -> summary and gate

Generation of the 500 candidate artifacts is deliberately not re-run here.
Those responses are cached under ``candidate_cache/`` and are the measured
data; regenerating them would silently replace the audit's observations.
Use ``python -m author_harness.generate --execute`` to fill missing trials.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = (
    ("gold annotation", "coordinator_private.build_audit_gold"),
    ("ambiguity audit", "coordinator_private.ambiguity_audit"),
    ("hidden suites", "coordinator_private.hidden_tests.generate_suites"),
    ("structural signatures", "coordinator_private.structural_metadata.compute"),
    ("audit release", "coordinator_private.release_audit"),
    ("candidate evaluation", "coordinator_private.evaluate_candidates"),
    ("summary and gate", "coordinator_private.summarize"),
)


def main() -> int:
    cached = sum(
        1
        for path in (ROOT / "candidate_cache").glob("*")
        if path.is_dir() and (path / "metadata.json").exists()
    )
    if cached != 500:
        print(
            f"candidate_cache holds {cached} trials; 500 are required.\n"
            "Run: python -m author_harness.generate --execute",
            file=sys.stderr,
        )
        return 1

    for label, module in STAGES:
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", module], cwd=ROOT, check=False
        )
        if result.returncode:
            print(f"stage failed: {label}", file=sys.stderr)
            return result.returncode

    gate = json.loads(
        (ROOT / "results/discrimination_gate.json").read_text(encoding="utf-8")
    )
    print(f"\npasses_gate={gate['passes_gate']} action={gate['recommended_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
