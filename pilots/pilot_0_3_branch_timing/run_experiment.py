#!/usr/bin/env python3
"""Run Pilot 0.3: branch-dependent bounded temporal obligations."""

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
    raise RuntimeError("Pilot 0.3 requires Python 3.11 or newer")

from src.explicit_conditional.generator import (
    compile_monitor,
    explicit_stage_add_metrics,
    explicit_structural_metrics,
    explicit_tree,
    generate_source,
)
from src.metrics import (
    python_ast_node_count,
    source_edit_measurements,
    source_measurements,
)
from src.model import stages_for_k, with_left_goal_rewired
from src.oracle import branch_timing_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parameter_structural_metrics,
    parameter_tree,
    parse_parameter_source,
)
from src.plotting import plot_all
from src.tl.evaluator import evaluate as evaluate_tl
from src.tl.generator import formula_tree, task_formula
from src.tl.syntax import pretty_task, structural_counts
from src.traces import (
    branch_rewire_probe_traces,
    deterministic_groups,
    flattened_deterministic_traces,
    structured_random_traces,
)
from src.tree_diff import TreeNode, ordered_tree_edit_distance

ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated"
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
REPRESENTATIONS = ("tl", "explicit_conditional", "parameterized")
BASE_RANDOM_SEED = 20_260_901
RANDOM_TRACES_PER_K = 10_000

CONSTRUCTION_COLUMNS = [
    "k",
    "representation",
    "characters",
    "lines",
    "tokens",
    "tl_ast_nodes",
    "tl_atoms",
    "tl_not",
    "tl_and",
    "tl_or",
    "tl_eventually",
    "tl_always",
    "tl_implication",
    "tl_bounded_eventually",
    "tl_ast_depth",
    "tl_decision_stages",
    "tl_branch_clauses",
    "tl_bounded_obligations",
    "explicit_states",
    "explicit_transitions",
    "explicit_variables",
    "explicit_selection_variables",
    "explicit_timestamp_variables",
    "explicit_completion_flags",
    "explicit_decision_branches",
    "explicit_goal_branches",
    "explicit_branches",
    "explicit_conditions",
    "explicit_deadline_checks",
    "explicit_numeric_bounds",
    "explicit_branch_mappings",
    "python_ast_nodes",
    "parameter_stage_count",
    "parameter_branch_count",
    "parameter_goal_mapping_count",
    "parameter_bound_count",
    "parameter_task_fields",
]

SEMANTICS_COLUMNS = [
    "k",
    "variant",
    "test_type",
    "num_trajectories",
    "tl_matches",
    "tl_mismatches",
    "explicit_matches",
    "explicit_mismatches",
    "parameterized_matches",
    "parameterized_mismatches",
    "random_seed",
]

STAGE_ADD_COLUMNS = [
    "k_before",
    "k_after",
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
    "stages_added",
    "branches_added",
    "goal_mappings_added",
    "bounds_added",
    "variables_added",
    "timestamps_added",
    "completion_flags_added",
    "decision_branches_added",
    "goal_checks_added",
]

BRANCH_REWIRE_COLUMNS = [
    "k",
    "modified_stage",
    "old_goal",
    "new_goal",
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
    "goal_mappings_changed",
    "existing_conditions_changed",
    "existing_dependencies_changed",
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


def _build_task(stages: Sequence[object]) -> dict[str, dict[str, object]]:
    formula = task_formula(stages)  # type: ignore[arg-type]
    tl_source = pretty_task(formula)
    explicit_source = generate_source(stages)  # type: ignore[arg-type]
    parameter_source = canonical_parameter_source(stages)  # type: ignore[arg-type]
    parsed_stages = parse_parameter_source(parameter_source)
    if tuple(stages) != parsed_stages:
        raise AssertionError("Parameterized task source did not round-trip")
    return {
        "tl": {
            "source": tl_source,
            "tree": formula_tree(formula),
            "formula": formula,
        },
        "explicit_conditional": {
            "source": explicit_source,
            "tree": explicit_tree(stages),  # type: ignore[arg-type]
            "monitor": compile_monitor(explicit_source),
        },
        "parameterized": {
            "source": parameter_source,
            "tree": parameter_tree(parsed_stages),
            "stages": parsed_stages,
        },
    }


def _write_generated_variant(
    k: int, variant: str, representations: dict[str, dict[str, object]]
) -> None:
    directory = GENERATED / f"B{k}" / variant
    directory.mkdir(parents=True, exist_ok=True)
    filenames = {
        "tl": "formula.btl",
        "explicit_conditional": "explicit_conditional_monitor.py",
        "parameterized": "task_config.py",
    }
    for representation, filename in filenames.items():
        source = representations[representation]["source"]
        tree = representations[representation]["tree"]
        assert isinstance(source, str) and isinstance(tree, TreeNode)
        (directory / filename).write_text(source, encoding="utf-8")
        (directory / f"{representation}_tree.json").write_text(
            _tree_json(tree), encoding="utf-8"
        )


def _semantic_row(
    *,
    k: int,
    variant: str,
    test_type: str,
    traces: Iterable[Sequence[str]],
    stages: Sequence[object],
    representations: dict[str, dict[str, object]],
    random_seed: int | str = "",
) -> dict[str, int | str]:
    formula = representations["tl"]["formula"]
    monitor = representations["explicit_conditional"]["monitor"]
    parameter_stages = representations["parameterized"]["stages"]
    assert callable(monitor) and isinstance(parameter_stages, tuple)
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
        expected = branch_timing_oracle(trajectory, stages)  # type: ignore[arg-type]
        values = {
            "tl": evaluate_tl(formula, trajectory),  # type: ignore[arg-type]
            "explicit": bool(monitor(trajectory)),
            "parameterized": evaluate_parameterized(trajectory, parameter_stages),
        }
        counts["num_trajectories"] += 1
        for representation, value in values.items():
            result = "matches" if value == expected else "mismatches"
            counts[f"{representation}_{result}"] += 1
    return {
        "k": k,
        "variant": variant,
        "test_type": test_type,
        **counts,
        "random_seed": random_seed,
    }


def _construction_rows(
    k: int,
    stages: Sequence[object],
    representations: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows = []
    for representation in REPRESENTATIONS:
        row: dict[str, int | str] = {column: "" for column in CONSTRUCTION_COLUMNS}
        source = representations[representation]["source"]
        assert isinstance(source, str)
        row.update(
            {
                "k": k,
                "representation": representation,
                **source_measurements(source),
            }
        )
        if representation == "tl":
            row.update(
                structural_counts(representations[representation]["formula"])  # type: ignore[arg-type]
            )
            row.update(
                {
                    "tl_decision_stages": k,
                    "tl_branch_clauses": 4 * k,
                    "tl_bounded_obligations": 2 * k,
                }
            )
        elif representation == "explicit_conditional":
            row.update(explicit_structural_metrics(source, stages))  # type: ignore[arg-type]
        else:
            row.update(parameter_structural_metrics(stages))  # type: ignore[arg-type]
        rows.append(row)
    return rows


def _common_edit(before: dict[str, object], after: dict[str, object]) -> dict[str, int]:
    before_source = before["source"]
    after_source = after["source"]
    before_tree = before["tree"]
    after_tree = after["tree"]
    assert isinstance(before_source, str) and isinstance(after_source, str)
    assert isinstance(before_tree, TreeNode) and isinstance(after_tree, TreeNode)
    return {
        "original_characters": len(before_source),
        "modified_characters": len(after_source),
        **source_edit_measurements(before_source, after_source),
        "tree_edit_distance": ordered_tree_edit_distance(before_tree, after_tree),
    }


def _stage_add_rows(
    k: int,
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows = []
    for representation in REPRESENTATIONS:
        row: dict[str, int | str] = {column: "" for column in STAGE_ADD_COLUMNS}
        row.update(
            {
                "k_before": k,
                "k_after": k + 1,
                "representation": representation,
                **_common_edit(before[representation], after[representation]),
                "stages_added": 1,
                "branches_added": 2,
                "goal_mappings_added": 2,
                "bounds_added": 2,
            }
        )
        if representation == "explicit_conditional":
            row.update(explicit_stage_add_metrics())
        rows.append(row)
    return rows


def _branch_rewire_rows(
    k: int,
    q: int,
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows = []
    for representation in REPRESENTATIONS:
        row: dict[str, int | str] = {column: "" for column in BRANCH_REWIRE_COLUMNS}
        row.update(
            {
                "k": k,
                "modified_stage": q,
                "old_goal": f"P{q}",
                "new_goal": f"X{q}",
                "representation": representation,
                **_common_edit(before[representation], after[representation]),
                "goal_mappings_changed": 1,
                "existing_conditions_changed": (
                    1 if representation == "explicit_conditional" else 0
                ),
                "existing_dependencies_changed": (
                    1 if representation == "explicit_conditional" else 0
                ),
            }
        )
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
            "Explicit conditional-monitor generator/compiler",
            ROOT / "src/explicit_conditional/generator.py",
        ),
        (
            "Parameterized conditional deadline-monitor engine",
            ROOT / "src/parameterized/monitor.py",
        ),
        ("Independent branch/timing oracle", ROOT / "src/oracle.py"),
        ("Deterministic and random trace generators", ROOT / "src/traces.py"),
        ("Source metrics", ROOT / "src/metrics.py"),
        ("Tree edit implementation", ROOT / "src/tree_diff.py"),
        ("Plotting utilities", ROOT / "src/plotting.py"),
        ("Benchmark runner", ROOT / "run_experiment.py"),
    ]
    rows = []
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
        "pilot": "0.3",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in package_names},
        "k_values": list(range(7)),
        "random_seed_base": BASE_RANDOM_SEED,
        "random_seed_rule": "base + k",
        "random_traces_per_k": RANDOM_TRACES_PER_K,
        "one_event_per_step": True,
        "named_non_O_events_at_most_once": True,
        "irrelevant_event": "O",
        "bounds": {"left": 8, "right": 10, "inclusive": True, "lower": 1},
        "stage_rewire_rule": "q=ceil(k/2); Pq becomes Xq",
        "k6_goal_reordering_resolution": {
            "full_reverse_expected": False,
            "reason": "stage-1 right distance is 11, exceeding bound 10",
            "successful_non_stage_order": [6, 5, 4, 1, 2, 3],
        },
        "canonical_python_formatter": "Black, line length 88",
        "source_diff": "SequenceMatcher with autojunk=False",
        "tree_edit": "APTED ordered tree edit distance; unit insert/delete/rename",
        "tl_fragment": [
            "Atom",
            "Not",
            "And",
            "Or",
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
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in paths
    ]
    (RESULTS / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _reset_output_directories()
    semantics_rows: list[dict[str, object]] = []
    base_tasks: dict[int, dict[str, dict[str, object]]] = {}

    for k in range(7):
        stages = stages_for_k(k)
        task = _build_task(stages)
        base_tasks[k] = task
        _write_generated_variant(k, "base", task)
        for test_type, traces in deterministic_groups(stages).items():
            semantics_rows.append(
                _semantic_row(
                    k=k,
                    variant="base",
                    test_type=test_type,
                    traces=traces,
                    stages=stages,
                    representations=task,
                )
            )
        if k:
            seed = BASE_RANDOM_SEED + k
            semantics_rows.append(
                _semantic_row(
                    k=k,
                    variant="base",
                    test_type="random_structured",
                    traces=structured_random_traces(
                        stages, count=RANDOM_TRACES_PER_K, seed=seed
                    ),
                    stages=stages,
                    representations=task,
                    random_seed=seed,
                )
            )

    stage_add_tasks: dict[int, dict[str, dict[str, object]]] = {}
    for k in range(6):
        stages = stages_for_k(k + 1)
        modified = _build_task(stages)
        stage_add_tasks[k] = modified
        _write_generated_variant(k, f"stage_add_B{k + 1}", modified)
        for representation in REPRESENTATIONS:
            if (
                modified[representation]["source"]
                != base_tasks[k + 1][representation]["source"]
            ):
                raise AssertionError("Stage-add variant is not canonical B(k+1)")
        semantics_rows.append(
            _semantic_row(
                k=k + 1,
                variant=f"stage_add_B{k + 1}",
                test_type="modified_stage_add",
                traces=flattened_deterministic_traces(stages),
                stages=stages,
                representations=modified,
            )
        )

    rewire_tasks: dict[int, tuple[int, dict[str, dict[str, object]]]] = {}
    for k in range(1, 7):
        original_stages = stages_for_k(k)
        q = (k + 1) // 2
        modified_stages = with_left_goal_rewired(original_stages, q)
        modified = _build_task(modified_stages)
        rewire_tasks[k] = (q, modified)
        _write_generated_variant(k, f"rewire_P{q}_to_X{q}", modified)
        traces = [
            *flattened_deterministic_traces(modified_stages),
            *branch_rewire_probe_traces(original_stages, q),
        ]
        semantics_rows.append(
            _semantic_row(
                k=k,
                variant=f"rewire_P{q}_to_X{q}",
                test_type="modified_branch_rewire",
                traces=traces,
                stages=modified_stages,
                representations=modified,
            )
        )

    mismatch_total = sum(
        int(row[column])
        for row in semantics_rows
        for column in (
            "tl_mismatches",
            "explicit_mismatches",
            "parameterized_mismatches",
        )
    )
    if mismatch_total:
        _write_csv(RESULTS / "semantics.csv", SEMANTICS_COLUMNS, semantics_rows)
        raise AssertionError(
            f"Semantic validation failed with {mismatch_total} mismatches"
        )

    construction_rows = [
        row
        for k in range(7)
        for row in _construction_rows(k, stages_for_k(k), base_tasks[k])
    ]
    stage_add_rows = [
        row
        for k in range(6)
        for row in _stage_add_rows(k, base_tasks[k], stage_add_tasks[k])
    ]
    rewire_rows = [
        row
        for k in range(1, 7)
        for row in _branch_rewire_rows(
            k, rewire_tasks[k][0], base_tasks[k], rewire_tasks[k][1]
        )
    ]

    paths = [
        RESULTS / "construction.csv",
        RESULTS / "semantics.csv",
        RESULTS / "stage_add_edit.csv",
        RESULTS / "branch_rewire_edit.csv",
        RESULTS / "infrastructure.csv",
    ]
    _write_csv(paths[0], CONSTRUCTION_COLUMNS, construction_rows)
    _write_csv(paths[1], SEMANTICS_COLUMNS, semantics_rows)
    _write_csv(paths[2], STAGE_ADD_COLUMNS, stage_add_rows)
    _write_csv(paths[3], BRANCH_REWIRE_COLUMNS, rewire_rows)
    _write_csv(paths[4], INFRASTRUCTURE_COLUMNS, _infrastructure_rows())
    _write_metadata()
    _write_checksums([*paths, RESULTS / "metadata.json"])
    plot_all(paths[0], paths[2], paths[3], PLOTS)

    evaluations = sum(int(row["num_trajectories"]) for row in semantics_rows)
    print(f"Pilot 0.3 complete: {evaluations:,} traces evaluated per representation")
    print("All TL, explicit, and parameterized results match the independent oracle")


if __name__ == "__main__":
    main()
