from __future__ import annotations

from src.explicit_fsm.generator import (
    fsm_modification_metrics,
    fsm_tree,
    generate_source,
)
from src.metrics import source_edit_measurements, source_measurements
from src.parameterized.monitor import (
    canonical_parameter_source,
    parameter_tree,
    parse_parameter_source,
)
from src.tl.generator import formula_tree, sequence_formula
from src.tl.syntax import pretty, structural_counts
from src.tree_diff import ordered_tree_edit_distance


def test_canonical_tl_formula_and_counts() -> None:
    formula = sequence_formula(["A1", "A2", "A3"])
    assert pretty(formula) == "F(A1 & F(A2 & F(A3)))"
    assert structural_counts(formula) == {
        "tl_ast_nodes": 8,
        "tl_atoms": 3,
        "tl_eventually": 3,
        "tl_and": 2,
        "tl_ast_depth": 6,
    }


def test_black_canonical_sources_round_trip() -> None:
    targets = ["A1", "A2", "A3"]
    parameter_source = canonical_parameter_source(targets)
    assert parse_parameter_source(parameter_source) == targets
    assert parameter_source.endswith("\n")
    fsm_source = generate_source(targets)
    assert 'state = "WAIT_A1"' in fsm_source
    assert 'state = "SUCCESS"' in fsm_source
    assert fsm_source.endswith("\n")


def test_normalized_tree_insertion_distances() -> None:
    before = ["A1", "A2", "A3", "A4"]
    after = ["A1", "A2", "X", "A3", "A4"]
    assert (
        ordered_tree_edit_distance(
            formula_tree(sequence_formula(before)),
            formula_tree(sequence_formula(after)),
        )
        == 3
    )
    assert ordered_tree_edit_distance(fsm_tree(before), fsm_tree(after)) == 5
    assert (
        ordered_tree_edit_distance(parameter_tree(before), parameter_tree(after)) == 1
    )


def test_fsm_insertion_metrics() -> None:
    metrics = fsm_modification_metrics(
        ["A1", "A2", "A3", "A4"],
        ["A1", "A2", "X", "A3", "A4"],
    )
    assert metrics == {
        "states_added": 1,
        "states_removed": 0,
        "transitions_added": 1,
        "transitions_removed": 0,
        "transitions_changed": 1,
        "conditions_added": 1,
        "conditions_removed": 0,
        "existing_dependencies_changed": 1,
    }


def test_source_measurements_and_diff_are_deterministic() -> None:
    before = canonical_parameter_source(["A1", "A2"])
    after = canonical_parameter_source(["A1", "X", "A2"])
    assert source_measurements(before) == source_measurements(before)
    assert source_edit_measurements(before, after) == source_edit_measurements(
        before, after
    )
    edit = source_edit_measurements(before, after)
    assert edit["source_lines_changed"] == 1
    assert edit["tokens_inserted"] > 0
