"""Deterministic prompt assembly from sanitized author-view files only."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def system_prompt() -> str:
    return (ROOT / "author_harness/system_prompt.txt").read_text(encoding="utf-8")


def user_prompt(view: Path, representation: str) -> str:
    if view.is_symlink() or any(path.is_symlink() for path in view.rglob("*")):
        raise AssertionError("author views must contain copied files, never symlinks")
    sections = [
        ("WAREHOUSE AND TRACE SEMANTICS", view / "warehouse.md"),
        ("REPRESENTATION DOCUMENTATION", view / "representation.md"),
    ]
    training = "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((view / "training_tasks").glob("train_*.txt"))
    )
    examples_path = view / "representation_examples.txt"
    examples = (
        examples_path.read_text(encoding="utf-8")
        if examples_path.exists()
        else "No representation-specific authored examples are supplied."
    )
    current = (view / "current_task.txt").read_text(encoding="utf-8")
    body: list[str] = []
    for title, path in sections:
        body.extend((f"\n## {title}\n", path.read_text(encoding="utf-8")))
    body.extend(
        (
            "\n## NATURAL-LANGUAGE TRAINING CARDS\n",
            training,
            "\n## REPRESENTATION-SPECIFIC TRAINING EXAMPLES\n",
            examples,
            "\n## CURRENT AUDIT TASK\n",
            current,
            "\n## OUTPUT\nReturn only the candidate artifact. This is the first and only attempt; no feedback will be provided.",
        )
    )
    return "\n".join(body)
