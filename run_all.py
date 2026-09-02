#!/usr/bin/env python3
"""Run tests and experiments for every pilot in a stable order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Pilot 1.1 publishes a verification runner instead of an experiment runner:
# its measured data are 500 cached model responses, and re-running the
# authoring stage would replace the audit's observations rather than
# reproduce them.
PILOTS = (
    (ROOT / "pilots/pilot_0_1_sequence", "run_experiment.py"),
    (ROOT / "pilots/pilot_0_2_timing", "run_experiment.py"),
    (ROOT / "pilots/pilot_0_3_branch_timing", "run_experiment.py"),
    (ROOT / "pilots/pilot_0_3b_abstraction_audit", "run_experiment.py"),
    (ROOT / "pilots/pilot_0_4_frozen_evolution", "run_experiment.py"),
    (ROOT / "pilots/pilot_1_0_heldout_benchmark", "run_experiment.py"),
    (ROOT / "pilots/pilot_1_1_blind_discrimination", "run_public.py"),
    (ROOT / "pilots/pilot_1_2_compositional_audit", "run_public.py"),
    (ROOT / "pilots/pilot_2_0_analysis_readiness", "run_experiment.py"),
)


def main() -> None:
    for pilot, runner in PILOTS:
        print(f"\n== {pilot.name}: tests ==", flush=True)
        subprocess.run([sys.executable, "-m", "pytest"], cwd=pilot, check=True)
        print(f"== {pilot.name}: {runner} ==", flush=True)
        subprocess.run([sys.executable, runner], cwd=pilot, check=True)
    print("\nAll pilots completed successfully.")


if __name__ == "__main__":
    main()
