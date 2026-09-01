#!/usr/bin/env python3
"""Run Pilot 0.2: overlapping bounded-timing dependencies."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("Pilot 0.2 requires Python 3.11 or newer")

from src.explicit_timed.generator import (
    compile_monitor,
    explicit_edit_metrics,
    explicit_structural_metrics,
    explicit_tree,
    generate_source,
)
from src.metrics import (
    python_ast_node_count,
    source_edit_measurements,
    source_measurements,
)
from src.model import (
    ALL_CONSTRAINTS,
    BASE_TARGETS,
    TimingConstraint,
    constraints_for_m,
    with_changed_bound,
)
from src.oracle import timed_sequence_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parameter_tree,
    parse_parameter_source,
)
from src.plotting import plot_all
from src.tl.evaluator import evaluate as evaluate_tl
from src.tl.generator import formula_tree, task_formula
from src.tl.syntax import pretty_task, structural_counts
from src.traces import (
    adjacent_swap_traces,
    gap_enumeration_traces,
    missing_target_traces,
)
from src.tree_diff import TreeNode, ordered_tree_edit_distance

ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated"
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
REPRESENTATIONS = ("tl", "explicit_timed", "parameterized")

CONSTRUCTION_COLUMNS = [
    "m",
    "representation",
    "characters",
    "lines",
    "tokens",
    "tl_ast_nodes",
    "tl_atoms",
    "tl_and",
    "tl_eventually",
    "tl_always",
    "tl_implication",
    "tl_bounded_eventually",
    "tl_ast_depth",
    "tl_timing_constraints",
    "explicit_states",
    "explicit_transitions",
    "explicit_branches",
    "explicit_conditions",
    "explicit_variables",
    "explicit_timing_variables",
    "explicit_timing_start_rules",
    "explicit_deadline_checks",
    "explicit_numeric_bounds",
    "parameter_target_count",
    "parameter_constraint_count",
    "parameter_constraint_fields",
    "python_ast_nodes",
]

SEMANTICS_COLUMNS = [
    "m",
    "variant",
    "test_type",
    "modified_constraint",
    "old_bound",
    "new_bound",
    "num_trajectories",
    "tl_matches",
    "tl_mismatches",
    "explicit_matches",
    "explicit_mismatches",
    "parameterized_matches",
    "parameterized_mismatches",
]

CONSTRAINT_ADD_COLUMNS = [
    "m_before",
    "m_after",
    "added_constraint",
    "representation",
    "original_characters",
    "modified_characters",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "tree_edit_distance",
    "constraints_added",
    "constraints_removed",
    "timing_variables_added",
    "timing_variables_removed",
    "timing_start_rules_added",
    "timing_start_rules_removed",
    "deadline_checks_added",
    "deadline_checks_removed",
    "existing_checks_changed",
    "bounds_changed",
]

NUMERIC_BOUND_COLUMNS = [
    "m",
    "modified_constraint",
    "old_bound",
    "new_bound",
    "representation",
    "original_characters",
    "modified_characters",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "tree_edit_distance",
    "bounds_changed",
    "existing_checks_changed",
]

INFRASTRUCTURE_COLUMNS = [
    "component",
    "characters",
    "lines",
    "tokens",
    "python_ast_nodes",
]


def _reset_output_directories() -> None:
    for directory in (GENERATED, RESULTS, PLOTS):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)


def _tree_json(tree: TreeNode) -> str:
    return json.dumps(tree.to_dict(), indent=2, sort_keys=True) + "\n"


def _build_task(
    constraints: Sequence[TimingConstraint],
) -> dict[str, dict[str, object]]:
    formula = task_formula(BASE_TARGETS, constraints)
    tl_source = pretty_task(formula)
    explicit_source = generate_source(BASE_TARGETS, constraints)
    parameter_source = canonical_parameter_source(BASE_TARGETS, constraints)
    parsed_targets, parsed_constraints = parse_parameter_source(parameter_source)
    if parsed_targets != list(BASE_TARGETS) or tuple(
        constraint.as_tuple() for constraint in parsed_constraints
    ) != tuple(constraint.as_tuple() for constraint in constraints):
        raise AssertionError("Parameterized task source did not round-trip")

    return {
        "tl": {
            "source": tl_source,
            "tree": formula_tree(formula),
            "formula": formula,
        },
        "explicit_timed": {
            "source": explicit_source,
            "tree": explicit_tree(BASE_TARGETS, constraints),
            "monitor": compile_monitor(explicit_source),
        },
        "parameterized": {
            "source": parameter_source,
            "tree": parameter_tree(BASE_TARGETS, constraints),
            "targets": parsed_targets,
            "constraints": parsed_constraints,
        },
    }


def _write_generated_variant(
    task_m: int,
    variant: str,
    representations: dict[str, dict[str, object]],
) -> None:
    directory = GENERATED / f"T{task_m}" / variant
    directory.mkdir(parents=True, exist_ok=True)
    filenames = {
        "tl": "formula.btl",
        "explicit_timed": "explicit_timed_monitor.py",
        "parameterized": "task_config.py",
    }
    for representation, filename in filenames.items():
        source = representations[representation]["source"]
        tree = representations[representation]["tree"]
        assert isinstance(source, str)
        assert isinstance(tree, TreeNode)
        (directory / filename).write_text(source, encoding="utf-8")
        (directory / f"{representation}_tree.json").write_text(
            _tree_json(tree), encoding="utf-8"
        )


def _semantic_row(
    *,
    m: int,
    variant: str,
    test_type: str,
    traces: Iterable[Sequence[str]],
    constraints: Sequence[TimingConstraint],
    representations: dict[str, dict[str, object]],
    modified_constraint: str = "",
    old_bound: int | str = "",
    new_bound: int | str = "",
) -> dict[str, int | str]:
    formula = representations["tl"]["formula"]
    explicit_monitor = representations["explicit_timed"]["monitor"]
    parameter_targets = representations["parameterized"]["targets"]
    parameter_constraints = representations["parameterized"]["constraints"]
    assert callable(explicit_monitor)
    assert isinstance(parameter_targets, list)
    assert isinstance(parameter_constraints, tuple)

    counts = {
        "num_trajectories": 0,
        "tl_matches": 0,
        "tl_mismatches": 0,
        "explicit_matches": 0,
        "explicit_mismatches": 0,
        "parameterized_matches": 0,
        "parameterized_mismatches": 0,
    }
    for trajectory in traces:
        expected = timed_sequence_oracle(trajectory, BASE_TARGETS, constraints)
        results = {
            "tl": evaluate_tl(formula, trajectory),  # type: ignore[arg-type]
            "explicit": bool(explicit_monitor(trajectory)),
            "parameterized": evaluate_parameterized(
                trajectory, parameter_targets, parameter_constraints
            ),
        }
        counts["num_trajectories"] += 1
        for representation, result in results.items():
            suffix = "matches" if result == expected else "mismatches"
            counts[f"{representation}_{suffix}"] += 1

    return {
        "m": m,
        "variant": variant,
        "test_type": test_type,
        "modified_constraint": modified_constraint,
        "old_bound": old_bound,
        "new_bound": new_bound,
        **counts,
    }


def _construction_rows(
    m: int,
    constraints: Sequence[TimingConstraint],
    representations: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for representation in REPRESENTATIONS:
        source = representations[representation]["source"]
        assert isinstance(source, str)
        row: dict[str, int | str] = {column: "" for column in CONSTRUCTION_COLUMNS}
        row.update(
            {
                "m": m,
                "representation": representation,
                **source_measurements(source),
            }
        )
        if representation == "tl":
            row.update(
                structural_counts(representations[representation]["formula"])  # type: ignore[arg-type]
            )
            row["tl_timing_constraints"] = m
        elif representation == "explicit_timed":
            row.update(explicit_structural_metrics(BASE_TARGETS, constraints))
            row["python_ast_nodes"] = python_ast_node_count(source)
        else:
            row.update(
                {
                    "parameter_target_count": len(BASE_TARGETS),
                    "parameter_constraint_count": m,
                    "parameter_constraint_fields": 3 * m,
                }
            )
        rows.append(row)
    return rows


def _common_edit_values(
    before: dict[str, object], after: dict[str, object]
) -> dict[str, int]:
    before_source = before["source"]
    after_source = after["source"]
    before_tree = before["tree"]
    after_tree = after["tree"]
    assert isinstance(before_source, str)
    assert isinstance(after_source, str)
    assert isinstance(before_tree, TreeNode)
    assert isinstance(after_tree, TreeNode)
    return {
        "original_characters": len(before_source),
        "modified_characters": len(after_source),
        **source_edit_measurements(before_source, after_source),
        "tree_edit_distance": ordered_tree_edit_distance(before_tree, after_tree),
    }


def _constraint_add_rows(
    m_before: int,
    before_constraints: Sequence[TimingConstraint],
    after_constraints: Sequence[TimingConstraint],
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    added_constraint = after_constraints[-1].name
    rows: list[dict[str, int | str]] = []
    for representation in REPRESENTATIONS:
        row: dict[str, int | str] = {column: "" for column in CONSTRAINT_ADD_COLUMNS}
        row.update(
            {
                "m_before": m_before,
                "m_after": m_before + 1,
                "added_constraint": added_constraint,
                "representation": representation,
                **_common_edit_values(before[representation], after[representation]),
                "constraints_added": 1,
                "constraints_removed": 0,
                "bounds_changed": 0,
            }
        )
        if representation == "explicit_timed":
            row.update(explicit_edit_metrics(before_constraints, after_constraints))
        rows.append(row)
    return rows


def _numeric_bound_rows(
    m: int,
    modified_constraint: str,
    before_constraints: Sequence[TimingConstraint],
    after_constraints: Sequence[TimingConstraint],
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for representation in REPRESENTATIONS:
        row: dict[str, int | str] = {column: "" for column in NUMERIC_BOUND_COLUMNS}
        row.update(
            {
                "m": m,
                "modified_constraint": modified_constraint,
                "old_bound": 8,
                "new_bound": 6,
                "representation": representation,
                **_common_edit_values(before[representation], after[representation]),
                "bounds_changed": 1,
            }
        )
        if representation == "explicit_timed":
            row["existing_checks_changed"] = explicit_edit_metrics(
                before_constraints, after_constraints
            )["existing_checks_changed"]
        rows.append(row)
    return rows


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _infrastructure_rows() -> list[dict[str, int | str]]:
    components = [
        ("Task-family model", ROOT / "src/model.py"),
        ("Bounded-TL syntax", ROOT / "src/tl/syntax.py"),
        ("Bounded-TL evaluator", ROOT / "src/tl/evaluator.py"),
        ("Bounded-TL generator", ROOT / "src/tl/generator.py"),
        (
            "Explicit timed-monitor generator/compiler",
            ROOT / "src/explicit_timed/generator.py",
        ),
        (
            "Parameterized deadline-monitor engine",
            ROOT / "src/parameterized/monitor.py",
        ),
        ("Independent timed-sequence oracle", ROOT / "src/oracle.py"),
        ("Systematic trace generators", ROOT / "src/traces.py"),
        ("Source metrics", ROOT / "src/metrics.py"),
        ("Tree edit implementation", ROOT / "src/tree_diff.py"),
        ("Plotting utilities", ROOT / "src/plotting.py"),
        ("Benchmark runner", ROOT / "run_experiment.py"),
    ]
    rows: list[dict[str, int | str]] = []
    for component, path in components:
        source = path.read_text(encoding="utf-8")
        rows.append(
            {
                "component": component,
                **source_measurements(source),
                "python_ast_nodes": python_ast_node_count(source),
            }
        )
    return rows


def _write_metadata() -> None:
    package_names = ["apted", "black", "matplotlib", "pandas", "pytest"]
    metadata = {
        "pilot": "0.2",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in package_names},
        "fixed_targets": list(BASE_TARGETS),
        "target_events_at_most_once": True,
        "irrelevant_event": "O",
        "gap_values": [0, 1, 2],
        "gap_trace_count_per_task": 3**9,
        "main_gap_evaluations_per_representation": 6 * (3**9),
        "sequence_failure_traces_per_task": 19,
        "timing_constraints": [
            {
                "name": constraint.name,
                "start": constraint.start,
                "end": constraint.end,
                "lower": constraint.lower,
                "bound": constraint.bound,
                "inclusive": True,
            }
            for constraint in ALL_CONSTRAINTS
        ],
        "numeric_modification": {"old_bound": 8, "new_bound": 6},
        "canonical_python_formatter": "Black, line length 88",
        "tokenizer": "Pilot 0.1 language-neutral tokenizer, unchanged",
        "source_diff": "SequenceMatcher with autojunk=False",
        "tree_edit": "APTED ordered tree edit distance; unit insert/delete/rename",
        "tl_fragment": [
            "Atom",
            "And",
            "Eventually",
            "Always",
            "Implication",
            "BoundedEventually",
        ],
        "timestamps_intentionally_omitted": True,
    }
    (RESULTS / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_checksums(paths: Sequence[Path]) -> None:
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (RESULTS / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _reset_output_directories()
    gap_traces = list(gap_enumeration_traces(BASE_TARGETS))
    missing_traces = missing_target_traces(BASE_TARGETS)
    swap_traces = adjacent_swap_traces(BASE_TARGETS)
    failure_traces = [*missing_traces, *swap_traces]
    if len(gap_traces) != 19_683 or len(failure_traces) != 19:
        raise AssertionError("Unexpected deterministic test-set size")

    semantic_rows: list[dict[str, object]] = []
    construction_rows: list[dict[str, object]] = []
    constraint_add_rows: list[dict[str, object]] = []
    numeric_bound_rows: list[dict[str, object]] = []
    base_tasks: dict[int, dict[str, dict[str, object]]] = {}

    for m in range(6):
        constraints = constraints_for_m(m)
        representations = _build_task(constraints)
        base_tasks[m] = representations
        _write_generated_variant(m, "base", representations)
        semantic_rows.extend(
            [
                _semantic_row(
                    m=m,
                    variant="base",
                    test_type="gap_enumeration",
                    traces=gap_traces,
                    constraints=constraints,
                    representations=representations,
                ),
                _semantic_row(
                    m=m,
                    variant="base",
                    test_type="missing_target",
                    traces=missing_traces,
                    constraints=constraints,
                    representations=representations,
                ),
                _semantic_row(
                    m=m,
                    variant="base",
                    test_type="adjacent_swap",
                    traces=swap_traces,
                    constraints=constraints,
                    representations=representations,
                ),
            ]
        )
        construction_rows.extend(_construction_rows(m, constraints, representations))

    for m_before in range(5):
        before_constraints = constraints_for_m(m_before)
        after_constraints = constraints_for_m(m_before + 1)
        modified = _build_task(after_constraints)
        variant = f"constraint_add_{after_constraints[-1].name}"
        _write_generated_variant(m_before, variant, modified)
        for representation in REPRESENTATIONS:
            if (
                modified[representation]["source"]
                != base_tasks[m_before + 1][representation]["source"]
            ):
                raise AssertionError("Constraint-add variant is not canonical")
        semantic_rows.extend(
            [
                _semantic_row(
                    m=m_before + 1,
                    variant=variant,
                    test_type="modified_constraint_addition_gap",
                    traces=gap_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=after_constraints[-1].name,
                ),
                _semantic_row(
                    m=m_before + 1,
                    variant=variant,
                    test_type="modified_constraint_addition_missing_target",
                    traces=missing_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=after_constraints[-1].name,
                ),
                _semantic_row(
                    m=m_before + 1,
                    variant=variant,
                    test_type="modified_constraint_addition_adjacent_swap",
                    traces=swap_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=after_constraints[-1].name,
                ),
            ]
        )
        constraint_add_rows.extend(
            _constraint_add_rows(
                m_before,
                before_constraints,
                after_constraints,
                base_tasks[m_before],
                modified,
            )
        )

    for m in range(1, 6):
        before_constraints = constraints_for_m(m)
        q = (m + 1) // 2
        after_constraints = with_changed_bound(before_constraints, q, 6)
        modified = _build_task(after_constraints)
        modified_constraint = f"C{q}"
        variant = f"numeric_{modified_constraint}_8_to_6"
        _write_generated_variant(m, variant, modified)
        semantic_rows.extend(
            [
                _semantic_row(
                    m=m,
                    variant=variant,
                    test_type="modified_numeric_bound_gap",
                    traces=gap_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=modified_constraint,
                    old_bound=8,
                    new_bound=6,
                ),
                _semantic_row(
                    m=m,
                    variant=variant,
                    test_type="modified_numeric_bound_missing_target",
                    traces=missing_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=modified_constraint,
                    old_bound=8,
                    new_bound=6,
                ),
                _semantic_row(
                    m=m,
                    variant=variant,
                    test_type="modified_numeric_bound_adjacent_swap",
                    traces=swap_traces,
                    constraints=after_constraints,
                    representations=modified,
                    modified_constraint=modified_constraint,
                    old_bound=8,
                    new_bound=6,
                ),
            ]
        )
        numeric_bound_rows.extend(
            _numeric_bound_rows(
                m,
                modified_constraint,
                before_constraints,
                after_constraints,
                base_tasks[m],
                modified,
            )
        )

    semantics_path = RESULTS / "semantics.csv"
    _write_csv(semantics_path, SEMANTICS_COLUMNS, semantic_rows)
    mismatch_total = sum(
        int(row[column])
        for row in semantic_rows
        for column in SEMANTICS_COLUMNS
        if column.endswith("_mismatches")
    )
    if mismatch_total:
        raise AssertionError(
            f"Semantic validation failed with {mismatch_total} mismatches; "
            "construction and edit metrics were not written"
        )

    construction_path = RESULTS / "construction.csv"
    constraint_add_path = RESULTS / "constraint_add_edit.csv"
    numeric_bound_path = RESULTS / "numeric_bound_edit.csv"
    infrastructure_path = RESULTS / "infrastructure.csv"
    _write_csv(construction_path, CONSTRUCTION_COLUMNS, construction_rows)
    _write_csv(constraint_add_path, CONSTRAINT_ADD_COLUMNS, constraint_add_rows)
    _write_csv(numeric_bound_path, NUMERIC_BOUND_COLUMNS, numeric_bound_rows)
    _write_csv(infrastructure_path, INFRASTRUCTURE_COLUMNS, _infrastructure_rows())
    _write_metadata()
    plot_all(construction_path, constraint_add_path, numeric_bound_path, PLOTS)
    _write_checksums(
        [
            construction_path,
            semantics_path,
            constraint_add_path,
            numeric_bound_path,
            infrastructure_path,
            RESULTS / "metadata.json",
        ]
    )

    main_gap_evaluations = sum(
        int(row["num_trajectories"])
        for row in semantic_rows
        if row["variant"] == "base" and row["test_type"] == "gap_enumeration"
    )
    modified_gap_evaluations = sum(
        int(row["num_trajectories"])
        for row in semantic_rows
        if str(row["test_type"]).endswith("_gap")
    )
    print("Pilot 0.2 complete")
    print(f"  Main gap evaluations per representation: {main_gap_evaluations:,}")
    print(
        f"  Modified gap evaluations per representation: {modified_gap_evaluations:,}"
    )
    print(f"  Semantic mismatches: {mismatch_total}")
    print(f"  Results: {RESULTS}")
    print(f"  Plots: {PLOTS}")


if __name__ == "__main__":
    main()
