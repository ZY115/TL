"""Coordinator-side checks for the released sacrificial audit."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from a1_ltlf.language import evaluate as evaluate_ltlf
from coordinator_private.build_audit_gold import CARDS, SELECTION, TEMPLATES, gold_tasks
from coordinator_private.oracle.ltlf_gold import compile_task
from coordinator_private.oracle.schema import task_from_dict
from coordinator_private.oracle.semantics import evaluate_task
from coordinator_private.summarize import discrimination_gate

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "coordinator_private"
LABELS = ("A", "B", "C", "D", "X")


def _step(value: str) -> frozenset[str]:
    return frozenset() if value == "O" else frozenset(value.split("+"))


def _decode(values: list[str]) -> tuple[frozenset[str], ...]:
    return tuple(_step(value) for value in values)


def _sample_traces(count: int, seed: int) -> list[tuple[frozenset[str], ...]]:
    rng = random.Random(seed)
    traces = []
    for _ in range(count):
        trace = []
        for _ in range(rng.randint(0, 12)):
            size = rng.choices((0, 1, 2), weights=(1, 8, 2), k=1)[0]
            trace.append(frozenset(rng.sample(LABELS, size)))
        traces.append(tuple(trace))
    return traces


def test_selection_matches_precommitted_buckets() -> None:
    difficulties = [candidate.split("_")[0] for _task, candidate in SELECTION]
    assert difficulties == ["low"] * 3 + ["medium"] * 4 + ["high"] * 3
    assert len({task for task, _ in SELECTION}) == 10


def test_every_gold_task_is_expressible_in_frozen_a1() -> None:
    """Protocol section 31: A1 UNSUPPORTED must mean author failure."""
    traces = _sample_traces(1_500, seed=4_242)
    for task in gold_tasks():
        formula = compile_task(task)
        for trace in traces:
            assert evaluate_task(task, trace) == evaluate_ltlf(formula, trace), (
                task.id,
                trace,
            )


def test_persisted_gold_round_trips() -> None:
    for task in gold_tasks():
        stored = task_from_dict(
            json.loads(
                (PRIVATE / "gold_ir/audit" / f"{task.id}.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        assert stored == task


@pytest.mark.parametrize("task_id", sorted(TEMPLATES))
def test_templates_hold_under_every_padding_offset(task_id: str) -> None:
    task = {item.id: item for item in gold_tasks()}[task_id]
    for kind, expected in (("positive", True), ("negative", False)):
        for entry in TEMPLATES[task_id][kind]:  # type: ignore[index]
            values = entry["trace"] if isinstance(entry, dict) else entry
            for before in range(3):
                for after in range(3):
                    padded = _decode(["O"] * before + list(values) + ["O"] * after)
                    assert evaluate_task(task, padded) is expected, (
                        task_id,
                        kind,
                        values,
                        before,
                        after,
                    )


@pytest.mark.parametrize("task_id", [task for task, _ in SELECTION])
def test_hidden_suite_labels_match_the_gold_oracle(task_id: str) -> None:
    task = {item.id: item for item in gold_tasks()}[task_id]
    path = PRIVATE / "hidden_tests" / f"{task_id}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4_500
    for row in rows:
        trace = tuple(frozenset(step) for step in row["trace"])
        assert evaluate_task(task, trace) is bool(row["expected"])
    assert any(row["expected"] for row in rows)
    assert any(not row["expected"] for row in rows)


def test_released_cards_match_the_annotated_text() -> None:
    for task_id, _candidate in SELECTION:
        released = (ROOT / "released_audit/task_cards" / f"{task_id}.txt").read_text(
            encoding="utf-8"
        )
        assert released.strip() == CARDS[task_id].strip()


def test_released_cards_leak_no_formal_notation() -> None:
    forbidden = (
        "Visit(", "Avoid(", "Ordered(", "Within(", "SafeUntil(", "Triggered(",
        "AnyOf(", "AllOf(", "eventually ", "after-each", "avoid_until", "F(", "G(",
    )
    for task_id, _candidate in SELECTION:
        text = (ROOT / "released_audit/task_cards" / f"{task_id}.txt").read_text(
            encoding="utf-8"
        )
        for token in forbidden:
            assert token not in text, (task_id, token)


def _task_row(task_id: str, a1: float, a2: float, a3: float) -> dict[str, object]:
    return {
        "task_id": task_id,
        "a1_class_rate": a1,
        "a2_class_rate": a2,
        "a3_class_rate": a3,
        "discriminative": round(max(a1, a2, a3) - min(a1, a2, a3), 6) >= 0.20,
    }


def _arm_rows() -> list[dict[str, object]]:
    return [
        {"representation": name, "unsupported_rate": 0.0}
        for name in ("a1", "a2_pooled", "a3")
    ]


def _ids() -> list[str]:
    """Synthetic gate inputs must carry the real ids, including the controls."""
    return [f"audit_{i:02d}" for i in range(1, 11)]


def test_gate_reports_ceiling_failure() -> None:
    tasks = [_task_row(task_id, 1.0, 1.0, 1.0) for task_id in _ids()]
    gate = discrimination_gate(tasks, _arm_rows(), [])
    assert gate["ceiling_failure"] is True
    assert gate["passes_gate"] is False
    assert gate["recommended_action"] == "increase_neutral_compositional_difficulty"


def test_gate_reports_floor_failure() -> None:
    tasks = [_task_row(task_id, 0.0, 0.0, 0.0) for task_id in _ids()]
    gate = discrimination_gate(tasks, _arm_rows(), [])
    assert gate["floor_failure"] is True
    assert gate["passes_gate"] is False
    assert gate["recommended_action"] == "reduce_difficulty"


def test_gate_passes_on_a_spread_without_ceiling_or_floor() -> None:
    ids = _ids()
    tasks = [_task_row(task_id, 0.8, 0.5, 0.4) for task_id in ids[:3]]
    tasks += [_task_row(task_id, 0.6, 0.6, 0.6) for task_id in ids[3:]]
    gate = discrimination_gate(tasks, _arm_rows(), [])
    assert gate["num_discriminative_tasks"] == 3
    assert gate["passes_gate"] is True
    assert gate["recommended_action"] == "proceed_to_full_benchmark"


def test_gate_rejects_results_missing_a_low_novelty_control() -> None:
    tasks = [_task_row(f"audit_{i:02d}", 0.5, 0.5, 0.5) for i in range(4, 11)]
    with pytest.raises(AssertionError, match="control tasks missing"):
        discrimination_gate(tasks, _arm_rows(), [])


def test_gate_never_recommends_a_representation_targeted_action() -> None:
    permitted = {
        "proceed_to_full_benchmark",
        "reduce_difficulty",
        "increase_neutral_compositional_difficulty",
        "resolve_task_ambiguity",
        "reconsider_hypothesis",
    }
    published = json.loads(
        (ROOT / "results/discrimination_gate.json").read_text(encoding="utf-8")
    )
    assert published["recommended_action"] in permitted


def test_no_measured_artifact_came_from_an_encoder() -> None:
    """Every scored artifact must originate from a cached model response."""
    for trial_dir in sorted((ROOT / "candidate_cache").iterdir()):
        if not trial_dir.is_dir():
            continue
        metadata = json.loads((trial_dir / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["provider"] == "ollama-local"
        assert (trial_dir / "raw_response.txt").exists()
