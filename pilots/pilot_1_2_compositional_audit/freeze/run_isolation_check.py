#!/usr/bin/env python3
"""Prove that exported author prompts carry no coordinator-private data.

Pilot 1.2's authoring channel is a fresh subagent that reads exactly one
exported prompt file placed outside the repository. Prompt-side isolation is
therefore checked here, once, before release: a random sentinel is written
into ``coordinator_private/``, every representation's prompt is built for one
training card, and the sentinel and every private path fragment must be
absent. Response-side isolation is enforced at ingest time, which refuses any
response containing the sentinel.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from author_harness.build_view import build_trial_view
from author_harness.prompts import sha256_text, system_prompt, user_prompt

ROOT = Path(__file__).resolve().parents[1]
REPRESENTATIONS = ("a1", "a2a", "a2b", "a2c", "a3")
PRIVATE_FRAGMENTS = (
    "coordinator_private",
    "gold_ir",
    "hidden_tests",
    "structural_metadata",
    "WithinThen",
    "SafeUntil(",
    "Triggered(",
    "pilot_1_1",
    "pilot_1_0",
)


def main() -> None:
    destination = ROOT / "freeze/isolation_check.json"
    sentinel_path = ROOT / "coordinator_private/isolation_sentinel.txt"
    if destination.exists():
        payload = json.loads(destination.read_text(encoding="utf-8"))
        if payload.get("isolation_check") != "passed":
            raise AssertionError("cached isolation check did not pass")
        print("Cached isolation sentinel check remains passed.")
        return
    sentinel = secrets.token_hex(32)
    sentinel_path.write_text(sentinel + "\n", encoding="utf-8")
    system = system_prompt()
    if sentinel in system:
        raise AssertionError("sentinel leaked into system prompt")
    card = ROOT / "public/training_tasks/train_12.txt"
    records = []
    for representation in REPRESENTATIONS:
        view = build_trial_view(f"isolation_{representation}", representation, card)
        prompt = user_prompt(view, representation)
        if sentinel in prompt:
            raise AssertionError(f"sentinel leaked into {representation} prompt")
        leaked = [fragment for fragment in PRIVATE_FRAGMENTS if fragment in prompt]
        if leaked:
            raise AssertionError(f"{representation} prompt contains private fragments {leaked}")
        records.append(
            {
                "representation": representation,
                "prompt_hash": sha256_text(prompt),
                "sentinel_absent_from_prompt": True,
                "private_fragments_absent": True,
            }
        )
    payload = {
        "isolation_check": "passed",
        "transport": "exported prompt file outside the repository; fresh memoryless subagent",
        "response_side_check": "ingest_trial refuses any response containing the sentinel",
        "sentinel_hash": hashlib.sha256(sentinel.encode()).hexdigest(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "author_environments": records,
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Prompt-side isolation check passed for A1, A2a/A2b/A2c, and A3.")


if __name__ == "__main__":
    main()
