#!/usr/bin/env python3
"""Run the complete Temporal Logic vs. Handwritten Monitor Pilot 0.1."""

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
    raise RuntimeError("Pilot 0.1 requires Python 3.11 or newer")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.explicit_fsm.generator import (
    compile_monitor,
    fsm_modification_metrics,
    fsm_structural_metrics,
    fsm_tree,
    generate_source,
)
from src.metrics import (
    python_ast_node_count,
    source_edit_measurements,
    source_measurements,
)
from src.oracle import sequence_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parameter_tree,
    parse_parameter_source,
)
from src.tl.evaluator import evaluate as evaluate_tl
from src.tl.generator import formula_tree, sequence_formula
from src.tl.syntax import pretty, structural_counts
from src.traces import (
    RANDOM_CATEGORY_COUNTS,
    exhaustive_traces,
    randomized_trace_groups,
)
from src.tree_diff import TreeNode, ordered_tree_edit_distance

ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / "generated"
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
BASE_RANDOM_SEED = 20_260_831
REPRESENTATIONS = ("tl", "explicit_fsm", "parameterized")
COLORS = {
    "tl": "#2563EB",
    "explicit_fsm": "#D97706",
    "parameterized": "#16803A",
}
LABELS = {
    "tl": "TL formula",
    "explicit_fsm": "Explicit FSM",
    "parameterized": "Parameterized monitor",
}

CONSTRUCTION_COLUMNS = [
    "n",
    "representation",
    "characters",
    "lines",
    "tokens",
    "tl_ast_nodes",
    "tl_atoms",
    "tl_eventually",
    "tl_and",
    "tl_ast_depth",
    "fsm_states",
    "fsm_transitions",
    "fsm_conditions",
    "fsm_variables",
    "fsm_branches",
    "parameter_count",
    "python_ast_nodes",
]

SEMANTICS_COLUMNS = [
    "n",
    "test_type",
    "num_trajectories",
    "tl_oracle_matches",
    "tl_oracle_mismatches",
    "fsm_oracle_matches",
    "fsm_oracle_mismatches",
    "parameterized_oracle_matches",
    "parameterized_oracle_mismatches",
    "random_seed",
]

STRUCTURAL_EDIT_COLUMNS = [
    "n",
    "representation",
    "original_characters",
    "modified_characters",
    "source_lines_inserted",
    "source_lines_deleted",
    "source_lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "tree_edit_distance",
    "states_added",
    "states_removed",
    "transitions_added",
    "transitions_removed",
    "transitions_changed",
    "conditions_added",
    "conditions_removed",
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


def _targets(n: int) -> list[str]:
    return [f"A{index}" for index in range(1, n + 1)]


def _modified_targets(targets: Sequence[str]) -> list[str]:
    # p = ceil(n/2), and Python index p is immediately after A_p.
    insertion_index = (len(targets) + 1) // 2
    return [*targets[:insertion_index], "X", *targets[insertion_index:]]


def _tree_json(tree: TreeNode) -> str:
    return json.dumps(tree.to_dict(), indent=2, sort_keys=True) + "\n"


def _build_representations(targets: Sequence[str]) -> dict[str, dict[str, object]]:
    formula = sequence_formula(targets)
    tl_source = pretty(formula) + "\n"
    fsm_source = generate_source(targets)
    parameter_source = canonical_parameter_source(targets)
    return {
        "tl": {
            "source": tl_source,
            "tree": formula_tree(formula),
            "formula": formula,
        },
        "explicit_fsm": {
            "source": fsm_source,
            "tree": fsm_tree(targets),
            "monitor": compile_monitor(fsm_source),
        },
        "parameterized": {
            "source": parameter_source,
            "tree": parameter_tree(targets),
            "targets": parse_parameter_source(parameter_source),
        },
    }


def _write_generated_task(
    n: int,
    variant: str,
    representations: dict[str, dict[str, object]],
) -> None:
    directory = GENERATED / f"S{n}" / variant
    directory.mkdir(parents=True, exist_ok=True)
    filenames = {
        "tl": "formula.tl",
        "explicit_fsm": "explicit_fsm.py",
        "parameterized": "targets.py",
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
    n: int,
    test_type: str,
    traces: Iterable[Sequence[str]],
    random_seed: int | str,
    targets: Sequence[str],
    representations: dict[str, dict[str, object]],
) -> dict[str, int | str]:
    formula = representations["tl"]["formula"]
    fsm_monitor = representations["explicit_fsm"]["monitor"]
    parameter_targets = representations["parameterized"]["targets"]
    assert callable(fsm_monitor)
    assert isinstance(parameter_targets, list)

    counts = {
        "num_trajectories": 0,
        "tl_oracle_matches": 0,
        "tl_oracle_mismatches": 0,
        "fsm_oracle_matches": 0,
        "fsm_oracle_mismatches": 0,
        "parameterized_oracle_matches": 0,
        "parameterized_oracle_mismatches": 0,
    }

    for trajectory in traces:
        expected = sequence_oracle(trajectory, targets)
        results = {
            "tl": evaluate_tl(formula, trajectory),  # type: ignore[arg-type]
            "fsm": bool(fsm_monitor(trajectory)),
            "parameterized": evaluate_parameterized(trajectory, parameter_targets),
        }
        counts["num_trajectories"] += 1
        for name, result in results.items():
            suffix = "matches" if result == expected else "mismatches"
            counts[f"{name}_oracle_{suffix}"] += 1

    return {
        "n": n,
        "test_type": test_type,
        **counts,
        "random_seed": random_seed,
    }


def _validate_modified_representations(
    targets: Sequence[str], representations: dict[str, dict[str, object]]
) -> None:
    """Smoke-check the generated insertion variant without changing test scope."""

    missing_x = [target for target in targets if target != "X"]
    samples = [
        [],
        list(targets),
        ["O", *targets, "O"],
        ["X", *targets],
        missing_x,
        [targets[0], targets[0], *targets[1:]],
    ]
    row = _semantic_row(
        n=len(targets),
        test_type="modified_smoke",
        traces=samples,
        random_seed="",
        targets=targets,
        representations=representations,
    )
    mismatch_keys = [key for key in row if key.endswith("_mismatches")]
    if any(int(row[key]) for key in mismatch_keys):
        raise AssertionError(f"Modified representation smoke check failed: {row}")


def _construction_rows(
    n: int,
    targets: Sequence[str],
    representations: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for representation in REPRESENTATIONS:
        source = representations[representation]["source"]
        assert isinstance(source, str)
        row: dict[str, int | str] = {column: "" for column in CONSTRUCTION_COLUMNS}
        row.update(
            {
                "n": n,
                "representation": representation,
                **source_measurements(source),
            }
        )
        if representation == "tl":
            row.update(
                structural_counts(representations[representation]["formula"])  # type: ignore[arg-type]
            )
        elif representation == "explicit_fsm":
            row.update(fsm_structural_metrics(targets))
            row["python_ast_nodes"] = python_ast_node_count(source)
        else:
            row["parameter_count"] = len(targets)
        rows.append(row)
    return rows


def _structural_edit_rows(
    n: int,
    before_targets: Sequence[str],
    after_targets: Sequence[str],
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for representation in REPRESENTATIONS:
        before_source = before[representation]["source"]
        after_source = after[representation]["source"]
        before_tree = before[representation]["tree"]
        after_tree = after[representation]["tree"]
        assert isinstance(before_source, str)
        assert isinstance(after_source, str)
        assert isinstance(before_tree, TreeNode)
        assert isinstance(after_tree, TreeNode)

        row: dict[str, int | str] = {column: "" for column in STRUCTURAL_EDIT_COLUMNS}
        row.update(
            {
                "n": n,
                "representation": representation,
                "original_characters": len(before_source),
                "modified_characters": len(after_source),
                **source_edit_measurements(before_source, after_source),
                "tree_edit_distance": ordered_tree_edit_distance(
                    before_tree, after_tree
                ),
            }
        )
        if representation == "explicit_fsm":
            row.update(fsm_modification_metrics(before_targets, after_targets))
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
        ("TL AST syntax", ROOT / "src/tl/syntax.py"),
        ("TL evaluator", ROOT / "src/tl/evaluator.py"),
        ("TL task generator", ROOT / "src/tl/generator.py"),
        ("Explicit FSM generator/compiler", ROOT / "src/explicit_fsm/generator.py"),
        (
            "Parameterized sequence-monitor engine",
            ROOT / "src/parameterized/monitor.py",
        ),
        ("Independent sequence oracle", ROOT / "src/oracle.py"),
        ("Trace generators", ROOT / "src/traces.py"),
        ("Source metrics", ROOT / "src/metrics.py"),
        ("Tree edit implementation", ROOT / "src/tree_diff.py"),
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


def _style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)


def _plot_construction(construction_path: Path) -> None:
    frame = pd.read_csv(construction_path)

    figure, axis = plt.subplots(figsize=(8, 5))
    for representation in REPRESENTATIONS:
        subset = frame[frame["representation"] == representation]
        axis.plot(
            subset["n"],
            subset["tokens"],
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )
    axis.set(
        xlabel="Sequence length n",
        ylabel="Task-specific lexical tokens",
        title="Task-specific source tokens",
    )
    axis.legend(frameon=False)
    _style_axis(axis)
    figure.tight_layout()
    figure.savefig(
        PLOTS / "construction_tokens.png",
        dpi=180,
        metadata={"Creator": "tl_sequence_pilot"},
    )
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    tl = frame[frame["representation"] == "tl"]
    axes[0].plot(tl["n"], tl["tl_ast_nodes"], marker="o", color=COLORS["tl"])
    axes[0].set(title="TL", xlabel="n", ylabel="TL AST nodes")

    fsm = frame[frame["representation"] == "explicit_fsm"]
    axes[1].plot(
        fsm["n"],
        fsm["fsm_states"],
        marker="o",
        color=COLORS["explicit_fsm"],
        label="states",
    )
    axes[1].plot(
        fsm["n"],
        fsm["fsm_transitions"],
        marker="s",
        linestyle="--",
        color="#9A5B05",
        label="transitions",
    )
    axes[1].set(title="Explicit FSM", xlabel="n", ylabel="Task-level count")
    axes[1].legend(frameon=False)

    parameterized = frame[frame["representation"] == "parameterized"]
    axes[2].plot(
        parameterized["n"],
        parameterized["parameter_count"],
        marker="o",
        color=COLORS["parameterized"],
    )
    axes[2].set(
        title="Parameterized monitor",
        xlabel="n",
        ylabel="Target entries",
    )
    for axis in axes:
        _style_axis(axis)
    figure.suptitle("Representation-specific structural metrics")
    figure.tight_layout()
    figure.savefig(
        PLOTS / "construction_structural_metrics.png",
        dpi=180,
        metadata={"Creator": "tl_sequence_pilot"},
    )
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5))
    for representation in REPRESENTATIONS:
        subset = frame[frame["representation"] == representation].sort_values("n")
        base_n = subset["n"].to_numpy()[:-1]
        marginal = subset["tokens"].to_numpy()[1:] - subset["tokens"].to_numpy()[:-1]
        axis.plot(
            base_n,
            marginal,
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )
    axis.set(
        xlabel="Starting sequence length n",
        ylabel="Δ tokens",
        title="Marginal tokens: ΔM(n) = M(n+1) − M(n)",
    )
    axis.legend(frameon=False)
    _style_axis(axis)
    figure.tight_layout()
    figure.savefig(
        PLOTS / "construction_marginal_tokens.png",
        dpi=180,
        metadata={"Creator": "tl_sequence_pilot"},
    )
    plt.close(figure)


def _plot_modification(structural_edit_path: Path) -> None:
    frame = pd.read_csv(structural_edit_path)

    figure, axis = plt.subplots(figsize=(8, 5))
    for representation in REPRESENTATIONS:
        subset = frame[frame["representation"] == representation]
        axis.plot(
            subset["n"],
            subset["tree_edit_distance"],
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )
    axis.set(
        xlabel="Original sequence length n",
        ylabel="Ordered tree edit distance",
        title="Structural edit footprint: normalized trees",
    )
    axis.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    _style_axis(axis)
    figure.tight_layout()
    figure.savefig(
        PLOTS / "modification_tree_edit_distance.png",
        dpi=180,
        metadata={"Creator": "tl_sequence_pilot"},
    )
    plt.close(figure)

    components = [
        ("tokens_inserted", "Inserted tokens"),
        ("tokens_deleted", "Deleted tokens"),
        ("tokens_changed", "Changed tokens"),
    ]
    figure, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True)
    for axis, (column, title) in zip(axes, components, strict=True):
        if (frame[column] == 0).all():
            axis.text(
                0.5,
                0.5,
                "All three representations\n0 for every n",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#5B6472",
                fontsize=12,
            )
            axis.set_ylim(-0.5, 0.5)
        else:
            for representation in REPRESENTATIONS:
                subset = frame[frame["representation"] == representation]
                axis.plot(
                    subset["n"],
                    subset[column],
                    marker="o",
                    color=COLORS[representation],
                    label=LABELS[representation],
                )
        axis.set(title=title, xlabel="n", ylabel="Task-specific tokens")
        _style_axis(axis)
    axes[0].legend(frameon=False, loc="upper left")
    figure.suptitle("Canonical token diff components")
    figure.tight_layout()
    figure.savefig(
        PLOTS / "modification_token_diff_components.png",
        dpi=180,
        metadata={"Creator": "tl_sequence_pilot"},
    )
    plt.close(figure)


def _write_metadata(modified_smoke_checks: int) -> None:
    package_names = ["apted", "black", "matplotlib", "pandas", "pytest"]
    metadata = {
        "pilot": "0.1",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in package_names},
        "base_random_seed": BASE_RANDOM_SEED,
        "random_seed_rule": "base_random_seed + n*100 + category_index",
        "random_category_counts": RANDOM_CATEGORY_COUNTS,
        "randomized_trajectories_per_n": sum(RANDOM_CATEGORY_COUNTS.values()),
        "canonical_python_formatter": "Black, line length 88",
        "tl_fragment": ["Atom", "And", "Eventually"],
        "tree_edit": "APTED ordered tree edit distance; unit insert/delete/rename",
        "modified_smoke_checks": modified_smoke_checks,
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
    construction_rows: list[dict[str, object]] = []
    semantic_rows: list[dict[str, object]] = []
    edit_rows: list[dict[str, object]] = []
    modified_smoke_checks = 0

    for n in range(1, 11):
        targets = _targets(n)
        modified_targets = _modified_targets(targets)
        original = _build_representations(targets)
        modified = _build_representations(modified_targets)
        _write_generated_task(n, "original", original)
        _write_generated_task(n, "modified_insert_X", modified)
        _validate_modified_representations(modified_targets, modified)
        modified_smoke_checks += 6

        if n <= 4:
            semantic_rows.append(
                _semantic_row(
                    n=n,
                    test_type="exhaustive",
                    traces=exhaustive_traces(targets),
                    random_seed="",
                    targets=targets,
                    representations=original,
                )
            )
        else:
            n_seed = BASE_RANDOM_SEED + n * 100
            randomized_total = 0
            for category, seed, traces in randomized_trace_groups(targets, n_seed):
                randomized_total += len(traces)
                semantic_rows.append(
                    _semantic_row(
                        n=n,
                        test_type=f"randomized_{category}",
                        traces=traces,
                        random_seed=seed,
                        targets=targets,
                        representations=original,
                    )
                )
            if randomized_total < 20_000:
                raise AssertionError(
                    f"n={n} generated only {randomized_total} randomized traces"
                )

        construction_rows.extend(_construction_rows(n, targets, original))
        edit_rows.extend(
            _structural_edit_rows(n, targets, modified_targets, original, modified)
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
    structural_edit_path = RESULTS / "structural_edit.csv"
    infrastructure_path = RESULTS / "infrastructure.csv"
    _write_csv(construction_path, CONSTRUCTION_COLUMNS, construction_rows)
    _write_csv(structural_edit_path, STRUCTURAL_EDIT_COLUMNS, edit_rows)
    _write_csv(
        infrastructure_path,
        INFRASTRUCTURE_COLUMNS,
        _infrastructure_rows(),
    )
    _write_metadata(modified_smoke_checks)
    _plot_construction(construction_path)
    _plot_modification(structural_edit_path)
    _write_checksums(
        [
            construction_path,
            structural_edit_path,
            semantics_path,
            infrastructure_path,
            RESULTS / "metadata.json",
        ]
    )

    exhaustive_total = sum(
        int(row["num_trajectories"])
        for row in semantic_rows
        if row["test_type"] == "exhaustive"
    )
    randomized_total = sum(
        int(row["num_trajectories"])
        for row in semantic_rows
        if str(row["test_type"]).startswith("randomized_")
    )
    print("Pilot 0.1 complete")
    print(f"  Exhaustive trajectories: {exhaustive_total:,}")
    print(f"  Randomized trajectories: {randomized_total:,}")
    print(f"  Semantic mismatches: {mismatch_total}")
    print(f"  Modified-variant smoke checks: {modified_smoke_checks}")
    print(f"  Results: {RESULTS}")
    print(f"  Plots: {PLOTS}")


if __name__ == "__main__":
    main()
