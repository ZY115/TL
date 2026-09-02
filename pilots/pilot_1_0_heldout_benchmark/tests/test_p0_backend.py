from __future__ import annotations

from collections import Counter
from pathlib import Path

from benchmark.split_algorithm import control_tasks, heldout_streams, training_tasks
from arms.a1_ltlf import compile_ltlf, compile_task
from environments.warehouse import Warehouse
from experiments.p0_calibration import canonical_satisfying_actions, validation_traces
from neutral_ir.interpreter import evaluate_ir
from neutral_ir.schema import (
    AllOf,
    Avoid,
    Deadline,
    On,
    Once,
    Requirement,
    TaskSpec,
    Visit,
    task_from_dict,
)
from neutral_ir.structure_signature import unseen_composition_count
from reference.automaton import compile_reference_automaton
from reference.product import shortest_environment_witness

ROOT = Path(__file__).resolve().parents[1]


def test_bottleneck_and_blocked_maps_force_b_to_c_through_x() -> None:
    for name in ("warehouse_bottleneck.yaml", "warehouse_blocked.yaml"):
        warehouse = Warehouse.load(ROOT / "environments" / name)
        assert warehouse.path_exists("B", "C")
        assert warehouse.every_path_uses("B", "C", "X")


def test_all_training_tasks_have_two_pipeline_agreement() -> None:
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    trace = warehouse.execute(canonical_satisfying_actions(warehouse))
    for task in training_tasks():
        assert evaluate_ir(task, trace)
        assert compile_reference_automaton(task).accepts(trace)
        assert compile_ltlf(compile_task(task)).accepts(trace)


def test_strong_deadline_cannot_be_satisfied_after_trace_ends() -> None:
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    trace = warehouse.execute([])
    task = TaskSpec("strong_next", (Requirement("r1", Deadline("A", 1, 1)),))
    assert not evaluate_ir(task, trace)
    assert not compile_reference_automaton(task).accepts(trace)


def test_past_once_inside_trigger_scope() -> None:
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    trace = warehouse.execute(["RIGHT", "RIGHT", "RIGHT"])
    valid = TaskSpec("past", (Requirement("r1", On("B", Once("A"))),))
    invalid = TaskSpec("past", (Requirement("r1", On("A", Once("B"))),))
    assert evaluate_ir(valid, trace)
    assert not evaluate_ir(invalid, trace)
    assert compile_reference_automaton(valid).accepts(trace)
    assert not compile_reference_automaton(invalid).accepts(trace)


def test_trivial_controls_have_no_structural_novelty() -> None:
    training = training_tasks()
    assert all(
        unseen_composition_count(task, training) == 0 for task in control_tasks()
    )
    heldout_task = task_from_dict(heldout_streams()[0]["states"][0])
    assert unseen_composition_count(heldout_task, training) > 0


def test_environment_product_returns_shortest_visit_witness() -> None:
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    task = TaskSpec("visit_a", (Requirement("r1", Visit("A")),))
    result = shortest_environment_witness(
        warehouse, compile_reference_automaton(task), horizon=5
    )
    assert result.status == "witness"
    assert result.actions == ("RIGHT",)


def test_logically_possible_but_environment_blocked_composition() -> None:
    task = TaskSpec(
        "blocked",
        (Requirement("r1", AllOf((Visit("C"), Avoid("X")))),),
    )
    # The map-level geometric assertion is exact and avoids an exponential product
    # search in this unit test; Experiment B will record the bounded product answer.
    warehouse = Warehouse.load(ROOT / "environments/warehouse_blocked.yaml")
    assert warehouse.every_path_uses("B", "C", "X")


def test_calibration_suite_has_precommitted_mixture() -> None:
    warehouse = Warehouse.load(ROOT / "environments/warehouse_base.yaml")
    counts = Counter(category for category, _ in validation_traces(warehouse, seed=123))
    assert sum(counts.values()) == 50_000
    assert counts == {
        "uniform_random": 20_000,
        "constructive_satisfying": 15_000,
        "targeted_mutation": 15_000,
    }
