#!/usr/bin/env python3
"""Run tests and experiments for every pilot in a stable order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PILOTS = (
    ROOT / "pilots/pilot_0_1_sequence",
    ROOT / "pilots/pilot_0_2_timing",
    ROOT / "pilots/pilot_0_3_branch_timing",
    ROOT / "pilots/pilot_0_3b_abstraction_audit",
    ROOT / "pilots/pilot_0_4_frozen_evolution",
    ROOT / "pilots/pilot_1_0_heldout_benchmark",
)


def main() -> None:
    for pilot in PILOTS:
        print(f"\n== {pilot.name}: tests ==", flush=True)
        subprocess.run([sys.executable, "-m", "pytest"], cwd=pilot, check=True)
        print(f"== {pilot.name}: experiment ==", flush=True)
        subprocess.run([sys.executable, "run_experiment.py"], cwd=pilot, check=True)
    print("\nAll pilots completed successfully.")


if __name__ == "__main__":
    main()
