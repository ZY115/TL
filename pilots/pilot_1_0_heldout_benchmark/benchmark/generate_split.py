"""Materialize the pre-committed split without exposing held-out data to designers."""

from __future__ import annotations

from pathlib import Path

from .split_algorithm import canonical_payloads


def materialize(root: Path) -> None:
    training, heldout, controls = canonical_payloads()
    outputs = {
        root / "train" / "catalog.json": training,
        root / "heldout" / "sealed_streams.json": heldout,
        root / "heldout" / "trivial_controls.json": controls,
    }
    for path, payload in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != payload:
            raise AssertionError(f"Frozen split drifted: {path}")
        path.write_bytes(payload)
