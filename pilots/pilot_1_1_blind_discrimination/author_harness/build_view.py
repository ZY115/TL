#!/usr/bin/env python3
"""Build sanitized, copy-only author views with no repository symlinks."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def _copy_file(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise AssertionError(f"author bundle source may not be a symlink: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def build_a2_design_view(name: str, seed_tag: int) -> Path:
    destination = ROOT / "author_views" / f"a2_design_{name}"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    _copy_file(PUBLIC / "warehouse.md", destination / "warehouse.md")
    _copy_file(
        PUBLIC / "a2_design_instructions.md", destination / "design_instructions.md"
    )
    for path in sorted((PUBLIC / "training_tasks").glob("*")):
        if path.is_file():
            _copy_file(path, destination / "training_tasks" / path.name)
    (destination / "design_seed_tag.txt").write_text(f"{seed_tag}\n", encoding="utf-8")
    assert not any(path.is_symlink() for path in destination.rglob("*"))
    return destination


def _representation_material(representation: str) -> tuple[Path, str | None]:
    if representation == "a1":
        return PUBLIC / "a1_ltlf_reference.md", None
    if representation == "a3":
        return PUBLIC / "a3_monitor_api.md", None
    design_name = {"a2a": "design_a", "a2b": "design_b", "a2c": "design_c"}[
        representation
    ]
    design = ROOT / "a2_designs" / design_name
    examples = "\n\n".join(
        f"### {path.name}\n{path.read_text(encoding='utf-8')}"
        for path in sorted((design / "training_artifacts").glob("*"))
        if path.is_file()
    )
    return design / "README.md", examples


def build_trial_view(trial_id: str, representation: str, task_card: Path) -> Path:
    destination = ROOT / "author_views" / trial_id
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    _copy_file(PUBLIC / "warehouse.md", destination / "warehouse.md")
    _copy_file(task_card, destination / "current_task.txt")
    documentation, examples = _representation_material(representation)
    _copy_file(documentation, destination / "representation.md")
    for path in sorted((PUBLIC / "training_tasks").glob("train_*.txt")):
        _copy_file(path, destination / "training_tasks" / path.name)
    if examples is not None:
        (destination / "representation_examples.txt").write_text(
            examples, encoding="utf-8"
        )
    assert not any(path.is_symlink() for path in destination.rglob("*"))
    return destination


def main() -> None:
    for name, seed in (("a", 11_101), ("b", 22_202), ("c", 33_303)):
        print(build_a2_design_view(name, seed))


if __name__ == "__main__":
    main()
