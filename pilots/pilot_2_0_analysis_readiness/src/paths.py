"""Wire Pilot 1.2 onto sys.path so its gold, language, and artifacts are reused.

Pilot 2.0 deliberately owns no oracle, no language, and no task pool. It
imports all three from Pilot 1.2 by reference so that the analysis is run on
exactly the artifacts that were measured there.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
PILOT_1_2 = PILOT.parent / "pilot_1_2_compositional_audit"

if str(PILOT_1_2) not in sys.path:
    sys.path.insert(0, str(PILOT_1_2))

LABELS = ("A", "B", "C", "D", "X")
