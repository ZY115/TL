#!/usr/bin/env python3
"""Freeze prompt assembly and the fixed authoring-channel configuration.

Pilot 1.2 authors through fresh memoryless subagents rather than a local
Ollama model, so no installed-model check is performed; the channel is
identified by the frozen ``model_config.json``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "freeze/freeze_manifest.json"


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        item
        for item in directory.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and ".pytest_cache" not in item.parts
    ):
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if any(
        str(manifest[f"a2{name}_tree_hash"]).startswith("pending")
        for name in ("a", "b", "c")
    ):
        raise AssertionError("authoring configuration cannot freeze before A2")
    config = json.loads(
        (ROOT / "author_harness/model_config.json").read_text(encoding="utf-8")
    )
    if config.get("provider") != "claude-subagent":
        raise RuntimeError("Pilot 1.2 expects the claude-subagent authoring channel")
    current_hash = tree_hash(ROOT / "author_harness")
    existing = manifest.get("author_prompt_hash")
    if existing != "pending_harness":
        if existing != current_hash or manifest.get("model_configuration") != config:
            raise AssertionError(
                "frozen authoring prompt or model configuration changed"
            )
        print("Authoring prompt and model configuration remain frozen.")
        return
    manifest["author_prompt_hash"] = current_hash
    manifest["model_configuration"] = config
    manifest["authoring_freeze_time"] = (
        datetime.now().astimezone().isoformat(timespec="seconds")
    )
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Fixed prompt assembly and subagent authoring channel frozen.")


if __name__ == "__main__":
    main()
