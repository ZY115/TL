#!/usr/bin/env python3
"""Prove that prompt-only author environments do not receive private sentinel data."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from author_harness.build_view import build_trial_view
from author_harness.generate import _ollama_generate
from author_harness.prompts import sha256_text, system_prompt, user_prompt

ROOT = Path(__file__).resolve().parents[1]
REPRESENTATIONS = ("a1", "a2a", "a2b", "a2c", "a3")


def main() -> None:
    destination = ROOT / "freeze/isolation_check.json"
    if destination.exists():
        payload = json.loads(destination.read_text(encoding="utf-8"))
        if payload.get("isolation_check") != "passed":
            raise AssertionError("cached isolation check did not pass")
        print("Cached isolation sentinel check remains passed.")
        return
    sentinel = secrets.token_hex(32)
    sentinel_path = ROOT / "coordinator_private/isolation_sentinel.txt"
    sentinel_path.write_text(sentinel + "\n", encoding="utf-8")
    system = system_prompt()
    if sentinel in system:
        raise AssertionError("sentinel leaked into system prompt")
    records = []
    card = ROOT / "public/training_tasks/train_13.txt"
    for index, representation in enumerate(REPRESENTATIONS):
        view = build_trial_view(f"isolation_{representation}", representation, card)
        prompt = user_prompt(view, representation)
        if sentinel in prompt:
            raise AssertionError(f"sentinel leaked into {representation} prompt")
        raw = _ollama_generate(system, prompt, seed=20_261_900 + index)
        response = str(raw["response"])
        if sentinel in response:
            raise AssertionError(f"sentinel leaked into {representation} response")
        records.append(
            {
                "representation": representation,
                "prompt_hash": sha256_text(prompt),
                "response_hash": sha256_text(response),
                "sentinel_absent_from_prompt": True,
                "sentinel_absent_from_response": True,
            }
        )
    payload = {
        "isolation_check": "passed",
        "transport": "prompt-only local Ollama HTTP request",
        "filesystem_capability_exposed_to_model": False,
        "sentinel_hash": hashlib.sha256(sentinel.encode()).hexdigest(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "author_environments": records,
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Isolation sentinel check passed for A1, A2a/A2b/A2c, and A3.")


if __name__ == "__main__":
    main()
