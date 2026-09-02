#!/usr/bin/env python3
"""Run all currently implemented Pilot 1.0 phases."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "run_experiment.py"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
