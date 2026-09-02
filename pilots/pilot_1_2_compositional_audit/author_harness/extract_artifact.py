"""Deterministic best-effort extraction of the single requested artifact."""

from __future__ import annotations

import re

_FENCE = re.compile(
    r"```(?:python|ltl|ltlf|text|dsl)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE
)


def extract_artifact(response: str) -> str:
    stripped = response.strip()
    if stripped == "UNSUPPORTED":
        return "UNSUPPORTED\n"
    matches = _FENCE.findall(stripped)
    if len(matches) == 1:
        stripped = matches[0].strip()
    return stripped + "\n"
