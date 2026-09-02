#!/usr/bin/env python3
"""Current one-command entry point: P0 plus the frozen-arm conformance gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    subprocess.run([sys.executable, "run_p0.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "run_freeze_validation.py"], cwd=ROOT, check=True)
    print("Pilot 1.0 P0 and the frozen-arm gate are complete. P1/P2 remain pending.")


if __name__ == "__main__":
    main()
