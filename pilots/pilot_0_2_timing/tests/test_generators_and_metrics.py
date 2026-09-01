from __future__ import annotations

from src.explicit_timed.generator import (
    explicit_edit_metrics,
    explicit_structural_metrics,
    explicit_tree,
    generate_source,
)
from src.metrics import source_edit_measurements, source_measurements
from src.model import BASE_TARGETS, constraints_for_m, with_changed_bound
from src.parameterized.monitor import (
    canonical_parameter_source,
    parameter_tree,
    parse_parameter_source,
)
from src.tl.generator import formula_tree, task_formula
from src.tl.syntax import pretty_task, structural_counts
from src.tree_diff import ordered_tree_edit_distance


def test_canonical_tl_source_and_counts() -> None:
    formula = task_formula(BASE_TARGETS, constraints_for_m(1))
    source = pretty_task(formula)
    lines = source.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("F(A1 & F(A2")
    assert lines[1] == "G(A1 -> F[1,8](A6))"
    assert structural_counts(formula) == {
        "tl_ast_nodes": 35,
        "tl_atoms": 12,
        "tl_and": 10,
        "tl_eventually": 10,
        "tl_always": 1,
        "tl_implication": 1,
        "tl_bounded_eventually": 1,
        "tl_ast_depth": 21,
    }


def test_parameterized_source_round_trip() -> None:
    constraints = constraints_for_m(3)
    source = canonical_parameter_source(BASE_TARGETS, constraints)
    targets, parsed = parse_parameter_source(source)
    assert targets == list(BASE_TARGETS)
    assert [item.as_tuple() for item in parsed] == [
        item.as_tuple() for item in constraints
    ]
    assert source.endswith("\n")


def test_explicit_structural_counts() -> None:
    assert explicit_structural_metrics(BASE_TARGETS, constraints_for_m(3)) == {
        "explicit_states": 11,
        "explicit_transitions": 10,
        "explicit_branches": 10,
        "explicit_conditions": 13,
        "explicit_variables": 4,
        "explicit_timing_variables": 3,
        "explicit_timing_start_rules": 3,
        "explicit_deadline_checks": 3,
        "explicit_numeric_bounds": 3,
    }


def test_constraint_add_tree_distances() -> None:
    before = constraints_for_m(2)
    after = constraints_for_m(3)
    assert (
        ordered_tree_edit_distance(
            formula_tree(task_formula(BASE_TARGETS, before)),
            formula_tree(task_formula(BASE_TARGETS, after)),
        )
        == 6
    )
    assert (
        ordered_tree_edit_distance(
            explicit_tree(BASE_TARGETS, before), explicit_tree(BASE_TARGETS, after)
        )
        == 7
    )
    assert (
        ordered_tree_edit_distance(
            parameter_tree(BASE_TARGETS, before),
            parameter_tree(BASE_TARGETS, after),
        )
        == 4
    )


def test_numeric_bound_tree_distances() -> None:
    before = constraints_for_m(4)
    after = with_changed_bound(before, 2, 6)
    assert (
        ordered_tree_edit_distance(
            formula_tree(task_formula(BASE_TARGETS, before)),
            formula_tree(task_formula(BASE_TARGETS, after)),
        )
        == 1
    )
    assert (
        ordered_tree_edit_distance(
            explicit_tree(BASE_TARGETS, before), explicit_tree(BASE_TARGETS, after)
        )
        == 1
    )
    assert (
        ordered_tree_edit_distance(
            parameter_tree(BASE_TARGETS, before),
            parameter_tree(BASE_TARGETS, after),
        )
        == 1
    )


def test_explicit_edit_metrics() -> None:
    addition = explicit_edit_metrics(constraints_for_m(2), constraints_for_m(3))
    assert addition == {
        "constraints_added": 1,
        "constraints_removed": 0,
        "timing_variables_added": 1,
        "timing_variables_removed": 0,
        "timing_start_rules_added": 1,
        "timing_start_rules_removed": 0,
        "deadline_checks_added": 1,
        "deadline_checks_removed": 0,
        "existing_checks_changed": 0,
        "bounds_changed": 0,
    }
    before = constraints_for_m(3)
    numeric = explicit_edit_metrics(before, with_changed_bound(before, 2, 6))
    assert numeric["bounds_changed"] == 1
    assert numeric["existing_checks_changed"] == 1


def test_source_metrics_are_deterministic() -> None:
    before = generate_source(BASE_TARGETS, constraints_for_m(2))
    after = generate_source(BASE_TARGETS, constraints_for_m(3))
    assert source_measurements(before) == source_measurements(before)
    assert source_edit_measurements(before, after) == source_edit_measurements(
        before, after
    )
    assert source_edit_measurements(before, after)["tokens_inserted"] > 0
