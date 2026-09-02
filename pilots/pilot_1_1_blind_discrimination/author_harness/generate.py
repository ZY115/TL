#!/usr/bin/env python3
"""Cache fixed-model first-attempt artifacts for the released blind audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from author_harness.build_view import build_trial_view
from author_harness.extract_artifact import extract_artifact
from author_harness.prompts import sha256_text, system_prompt, user_prompt

ROOT = Path(__file__).resolve().parents[1]
REPRESENTATIONS = ("a1", "a2a", "a2b", "a2c", "a3")
REPLICATES = 10


def _config() -> dict[str, object]:
    return json.loads(
        (ROOT / "author_harness/model_config.json").read_text(encoding="utf-8")
    )


def _trial_seed(task_index: int, representation_index: int, replicate: int) -> int:
    return 20_261_100 + task_index * 1_000 + representation_index * 100 + replicate


def _ollama_generate(system: str, prompt: str, seed: int) -> dict[str, object]:
    config = _config()
    payload = {
        "model": config["model"],
        "system": system,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": config["temperature"],
            "top_p": config["top_p"],
            "seed": seed,
            "num_predict": config["num_predict"],
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())


def _manifest_ready() -> None:
    manifest = json.loads(
        (ROOT / "freeze/freeze_manifest.json").read_text(encoding="utf-8")
    )
    for key in ("a2a_tree_hash", "a2b_tree_hash", "a2c_tree_hash"):
        if str(manifest.get(key, "")).startswith("pending"):
            raise RuntimeError("candidate generation is forbidden before A2 freeze")
    if manifest.get("audit_release_status") != "released_after_complete_freeze":
        raise RuntimeError("candidate generation is forbidden before audit release")


def run(*, execute: bool) -> int:
    _manifest_ready()
    cards = sorted((ROOT / "released_audit/task_cards").glob("audit_*.txt"))
    if len(cards) != 10:
        raise RuntimeError("exactly ten released audit task cards are required")
    config = _config()
    system = system_prompt()
    generated = 0
    for task_index, card in enumerate(cards):
        for representation_index, representation in enumerate(REPRESENTATIONS):
            for replicate in range(REPLICATES):
                trial_id = f"{card.stem}__{representation}__r{replicate:02d}"
                view = build_trial_view(trial_id, representation, card)
                prompt = user_prompt(view, representation)
                seed = _trial_seed(task_index, representation_index, replicate)
                cache_key = hashlib.sha256(
                    json.dumps(
                        {
                            "config": config,
                            "seed": seed,
                            "system_hash": sha256_text(system),
                            "user_hash": sha256_text(prompt),
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                trial_dir = ROOT / "candidate_cache" / trial_id
                metadata_path = trial_dir / "metadata.json"
                if metadata_path.exists():
                    # A cached trial is only a valid replay of *this* prompt and
                    # model configuration. Silently reusing an artifact produced
                    # under different inputs would publish a stale measurement.
                    cached = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if cached.get("cache_key") != cache_key:
                        raise RuntimeError(
                            f"{trial_id}: cached trial was produced under a "
                            "different prompt or model configuration; delete the "
                            "cache entry deliberately before regenerating"
                        )
                    continue
                if not execute:
                    generated += 1
                    continue
                trial_dir.mkdir(parents=True, exist_ok=True)
                raw = _ollama_generate(system, prompt, seed)
                response = str(raw["response"])
                artifact = extract_artifact(response)
                (trial_dir / "raw_response.txt").write_text(response, encoding="utf-8")
                (trial_dir / "artifact.txt").write_text(artifact, encoding="utf-8")
                metadata = {
                    "trial_id": trial_id,
                    "task_id": card.stem,
                    "representation": representation,
                    "replicate": replicate,
                    "provider": config["provider"],
                    "model": config["model"],
                    "model_revision": config["model_revision"],
                    "temperature": config["temperature"],
                    "top_p": config["top_p"],
                    "seed": seed,
                    "system_prompt_hash": sha256_text(system),
                    "user_prompt_hash": sha256_text(prompt),
                    "response_hash": sha256_text(response),
                    "artifact_hash": sha256_text(artifact),
                    "cache_key": cache_key,
                    "timestamp": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                }
                metadata_path.write_text(
                    json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                generated += 1
                print(f"cached {trial_id}", flush=True)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="call the fixed local model; without this flag only count missing trials",
    )
    args = parser.parse_args()
    count = run(execute=args.execute)
    print(f"{'generated' if args.execute else 'missing'} trials: {count}")


if __name__ == "__main__":
    main()
