from __future__ import annotations

from pathlib import Path

from author_harness.build_view import build_trial_view
from author_harness.extract_artifact import extract_artifact
from author_harness.prompts import system_prompt, user_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_all_representation_views_are_copy_only_and_private_free() -> None:
    card = ROOT / "public/training_tasks/train_04.txt"
    forbidden = (
        "coordinator_private",
        "Neutral IR",
        "OrderedVisit",
        "MaintainUntil",
        "pilot_1_0",
    )
    for representation in ("a1", "a2a", "a2b", "a2c", "a3"):
        view = build_trial_view(f"test_{representation}", representation, card)
        assert not any(path.is_symlink() for path in view.rglob("*"))
        prompt = user_prompt(view, representation)
        assert all(value not in prompt for value in forbidden)


def test_prompt_assembly_is_deterministic() -> None:
    card = ROOT / "public/training_tasks/train_05.txt"
    view = build_trial_view("test_stable", "a1", card)
    assert user_prompt(view, "a1") == user_prompt(view, "a1")
    assert system_prompt() == system_prompt()


def test_artifact_extraction_is_deterministic() -> None:
    assert extract_artifact("```ltlf\nF at_A\n```") == "F at_A\n"
    assert extract_artifact("UNSUPPORTED") == "UNSUPPORTED\n"
    assert extract_artifact("F at_A") == "F at_A\n"
