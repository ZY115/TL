#!/usr/bin/env python3
"""Print the exact sanitized author prompt for one trial.

The blind-authoring contract is that an author receives the prompt text and
nothing else. This script emits that text verbatim so a different authoring
channel — a hosted model, a fresh subagent, or a human — can be given the same
input the local-model harness used, with no filesystem access of its own.

    python -m author_harness.export_prompt audit_01 a1

Adding ``--system`` prints the system prompt instead of the user prompt.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from author_harness.build_view import build_trial_view
from author_harness.prompts import sha256_text, system_prompt, user_prompt

ROOT = Path(__file__).resolve().parents[1]
REPRESENTATIONS = ("a1", "a2a", "a2b", "a2c", "a3")


def build(task_id: str, representation: str) -> tuple[str, str]:
    if representation not in REPRESENTATIONS:
        raise SystemExit(f"unknown representation {representation!r}")
    card = ROOT / "released_audit/task_cards" / f"{task_id}.txt"
    if not card.exists():
        raise SystemExit(f"no released card for {task_id!r}")
    view = build_trial_view(f"export__{task_id}__{representation}", representation, card)
    return system_prompt(), user_prompt(view, representation)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("representation")
    parser.add_argument("--system", action="store_true")
    parser.add_argument("--hash-only", action="store_true")
    args = parser.parse_args()

    system, user = build(args.task_id, args.representation)
    text = system if args.system else user
    if args.hash_only:
        print(sha256_text(text))
        return
    print(text)


if __name__ == "__main__":
    main()
