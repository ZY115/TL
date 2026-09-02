#!/usr/bin/env python3
"""Record one blind-authored artifact in the candidate cache.

The authoring channel for Pilot 1.2 is a fresh, memoryless subagent that
receives exactly one exported prompt and no repository access. The transport
cannot be driven from inside a Python script, so the coordinator exports the
prompt (``export_prompt``), hands it to the agent, and records the agent's raw
final message here. Everything ``evaluate_candidates`` needs is written:

    candidate_cache/<task>__<arm>__r<NN>/
        raw_response.txt
        artifact.txt
        metadata.json

The stored ``cache_key`` binds the artifact to the exact system prompt, user
prompt, model, and replicate it was produced under, exactly as the local-model
harness did, so a later prompt change cannot silently reuse a stale artifact.

    python -m author_harness.ingest_trial audit_03 a2b 0 response.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from author_harness.export_prompt import build
from author_harness.extract_artifact import extract_artifact
from author_harness.prompts import sha256_text

ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict[str, object]:
    return json.loads((ROOT / "author_harness/model_config.json").read_text(encoding="utf-8"))


def ingest(task_id: str, representation: str, replicate: int, response: str) -> Path:
    config = _config()
    system, prompt = build(task_id, representation)
    trial_id = f"{task_id}__{representation}__r{replicate:02d}"
    trial_dir = ROOT / "candidate_cache" / trial_id
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "config": config,
                "replicate": replicate,
                "system_hash": sha256_text(system),
                "user_hash": sha256_text(prompt),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    metadata_path = trial_dir / "metadata.json"
    if metadata_path.exists():
        cached = json.loads(metadata_path.read_text(encoding="utf-8"))
        if cached.get("cache_key") == cache_key:
            raise SystemExit(f"{trial_id} is already cached under this exact prompt")
        raise SystemExit(
            f"{trial_id} exists under a different prompt or configuration; "
            "delete it deliberately before re-ingesting"
        )
    sentinel_path = ROOT / "coordinator_private/isolation_sentinel.txt"
    if sentinel_path.exists() and sentinel_path.read_text().strip() in response:
        raise SystemExit(f"{trial_id}: response contains the isolation sentinel; boundary breached")
    artifact = extract_artifact(response)
    trial_dir.mkdir(parents=True)
    (trial_dir / "raw_response.txt").write_text(response, encoding="utf-8")
    (trial_dir / "artifact.txt").write_text(artifact, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "trial_id": trial_id,
                "task_id": task_id,
                "representation": representation,
                "replicate": replicate,
                "provider": config["provider"],
                "model": config["model"],
                "model_revision": config["model_revision"],
                "temperature": config.get("temperature"),
                "top_p": config.get("top_p"),
                "seed": None,
                "system_prompt_hash": sha256_text(system),
                "user_prompt_hash": sha256_text(prompt),
                "response_hash": sha256_text(response),
                "artifact_hash": sha256_text(artifact),
                "cache_key": cache_key,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return trial_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("representation")
    parser.add_argument("replicate", type=int)
    parser.add_argument("response_file", type=Path)
    args = parser.parse_args()
    trial_dir = ingest(
        args.task_id,
        args.representation,
        args.replicate,
        args.response_file.read_text(encoding="utf-8"),
    )
    print(f"cached {trial_dir.name}")


if __name__ == "__main__":
    main()
