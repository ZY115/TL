"""Separate raw-metric plots for Pilot 0.2."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPRESENTATIONS = ("tl", "explicit_timed", "parameterized")
COLORS = {
    "tl": "#2563EB",
    "explicit_timed": "#D97706",
    "parameterized": "#16803A",
}
LABELS = {
    "tl": "Bounded TL",
    "explicit_timed": "Explicit timed monitor",
    "parameterized": "Parameterized deadline monitor",
}


def _style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)


def _save(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, metadata={"Creator": "pilot_0_2_timing"})
    plt.close(figure)


def _plot_representation_lines(
    axis: plt.Axes,
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
) -> None:
    for representation in REPRESENTATIONS:
        subset = frame[frame["representation"] == representation]
        axis.plot(
            subset[x_column],
            subset[y_column],
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )


def _plot_token_components(
    frame: pd.DataFrame,
    x_column: str,
    title: str,
    path: Path,
) -> None:
    components = [
        ("tokens_inserted", "Inserted tokens"),
        ("tokens_deleted", "Deleted tokens"),
        ("tokens_changed", "Changed tokens"),
    ]
    figure, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True)
    for axis, (column, panel_title) in zip(axes, components, strict=True):
        if (frame[column] == 0).all():
            axis.text(
                0.5,
                0.5,
                "All three representations\n0 for every task",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#5B6472",
                fontsize=11,
            )
            axis.set_ylim(-0.5, 0.5)
        elif frame[column].nunique() == 1:
            value = frame[column].iloc[0]
            axis.text(
                0.5,
                0.5,
                f"All three representations\n{value:g} for every task",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#5B6472",
                fontsize=11,
            )
            axis.set_ylim(value - 0.5, value + 0.5)
        else:
            _plot_representation_lines(axis, frame, x_column, column)
        axis.set(
            title=panel_title,
            xlabel=x_column.replace("_", " "),
            ylabel="Task-specific tokens",
        )
        axis.set_xlim(frame[x_column].min(), frame[x_column].max())
        _style_axis(axis)
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(handles, labels, frameon=False, loc="best")
    figure.suptitle(title)
    _save(figure, path)


def plot_all(
    construction_path: Path,
    constraint_add_path: Path,
    numeric_bound_path: Path,
    output_directory: Path,
) -> None:
    construction = pd.read_csv(construction_path)
    addition = pd.read_csv(constraint_add_path)
    numeric = pd.read_csv(numeric_bound_path)

    figure, axis = plt.subplots(figsize=(8, 5))
    _plot_representation_lines(axis, construction, "m", "tokens")
    axis.set(
        xlabel="Number of timing constraints m",
        ylabel="Task-specific lexical tokens",
        title="Task-specific source tokens",
    )
    axis.legend(frameon=False)
    _style_axis(axis)
    _save(figure, output_directory / "construction_tokens.png")

    tl = construction[construction["representation"] == "tl"]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    operator_metrics = [
        ("tl_atoms", "atoms", "o"),
        ("tl_and", "and", "s"),
        ("tl_eventually", "eventually", "^"),
        ("tl_always", "always", "D"),
        ("tl_implication", "implication", "v"),
        ("tl_bounded_eventually", "bounded eventually", "P"),
    ]
    for column, label, marker in operator_metrics:
        axes[0].plot(tl["m"], tl[column], marker=marker, label=label)
    axes[0].set(
        title="Operator/node-type counts",
        xlabel="m",
        ylabel="TL node count",
    )
    axes[0].legend(frameon=False, ncol=2, fontsize=9)
    axes[1].plot(tl["m"], tl["tl_ast_nodes"], marker="o", label="total AST nodes")
    axes[1].plot(tl["m"], tl["tl_ast_depth"], marker="s", label="maximum depth")
    axes[1].set(title="Whole-tree metrics", xlabel="m", ylabel="Count")
    axes[1].legend(frameon=False)
    for axis in axes:
        _style_axis(axis)
    figure.suptitle("Bounded-TL structural metrics")
    _save(figure, output_directory / "construction_tl_structural.png")

    explicit = construction[construction["representation"] == "explicit_timed"]
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    panels: Sequence[tuple[plt.Axes, Sequence[tuple[str, str]]]] = [
        (
            axes[0, 0],
            (
                ("explicit_states", "states"),
                ("explicit_transitions", "sequence transitions"),
            ),
        ),
        (
            axes[0, 1],
            (
                ("explicit_branches", "branches"),
                ("explicit_conditions", "task-specific conditions"),
            ),
        ),
        (
            axes[1, 0],
            (
                ("explicit_variables", "task-specific variables"),
                ("explicit_timing_variables", "timing variables"),
            ),
        ),
        (
            axes[1, 1],
            (
                ("explicit_timing_start_rules", "timing-start rules"),
                ("explicit_deadline_checks", "deadline checks"),
                ("explicit_numeric_bounds", "numeric bounds"),
            ),
        ),
    ]
    for axis, metrics in panels:
        for marker_index, (column, label) in enumerate(metrics):
            axis.plot(
                explicit["m"],
                explicit[column],
                marker=("o", "s", "^")[marker_index],
                label=label,
            )
        axis.set(xlabel="m", ylabel="Count")
        axis.legend(frameon=False, fontsize=9)
        _style_axis(axis)
    figure.suptitle("Explicit timed-monitor structural metrics")
    _save(figure, output_directory / "construction_explicit_structural.png")

    parameterized = construction[construction["representation"] == "parameterized"]
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(
        parameterized["m"],
        parameterized["parameter_target_count"],
        marker="o",
        label="target count",
    )
    axis.plot(
        parameterized["m"],
        parameterized["parameter_constraint_count"],
        marker="s",
        label="constraint count",
    )
    axis.plot(
        parameterized["m"],
        parameterized["parameter_constraint_fields"],
        marker="^",
        label="constraint fields",
    )
    axis.set(
        xlabel="m",
        ylabel="Count",
        title="Parameterized task-configuration metrics",
    )
    axis.legend(frameon=False)
    _style_axis(axis)
    _save(figure, output_directory / "construction_parameterized_metrics.png")

    figure, axis = plt.subplots(figsize=(8, 5))
    for representation in REPRESENTATIONS:
        subset = construction[
            construction["representation"] == representation
        ].sort_values("m")
        base_m = subset["m"].to_numpy()[:-1]
        delta = subset["tokens"].to_numpy()[1:] - subset["tokens"].to_numpy()[:-1]
        axis.plot(
            base_m,
            delta,
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )
    axis.set(
        xlabel="Starting constraint count m",
        ylabel="Δ tokens",
        title="Marginal tokens when adding C(m+1)",
    )
    axis.legend(frameon=False)
    _style_axis(axis)
    _save(figure, output_directory / "construction_marginal_tokens.png")

    figure, axis = plt.subplots(figsize=(8, 5))
    _plot_representation_lines(axis, addition, "m_before", "tree_edit_distance")
    axis.set(
        xlabel="Constraints before addition m",
        ylabel="Ordered tree edit distance",
        title="Constraint-addition structural edit footprint",
    )
    axis.legend(frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
    _style_axis(axis)
    _save(figure, output_directory / "constraint_add_tree_edit.png")

    _plot_token_components(
        addition,
        "m_before",
        "Constraint-addition canonical token edits",
        output_directory / "constraint_add_token_edits.png",
    )

    figure, axis = plt.subplots(figsize=(8, 5))
    if numeric["tree_edit_distance"].nunique() == 1:
        value = numeric["tree_edit_distance"].iloc[0]
        axis.text(
            0.5,
            0.5,
            f"All three representations\n{value:g} for every task",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color="#5B6472",
            fontsize=13,
        )
        axis.set_ylim(value - 0.5, value + 0.5)
        axis.set_xlim(numeric["m"].min(), numeric["m"].max())
    else:
        _plot_representation_lines(axis, numeric, "m", "tree_edit_distance")
    axis.set(
        xlabel="Active timing constraints m",
        ylabel="Ordered tree edit distance",
        title="Numeric-bound structural edit footprint: 8 → 6",
    )
    handles, labels = axis.get_legend_handles_labels()
    if handles:
        axis.legend(
            handles,
            labels,
            frameon=False,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
        )
    _style_axis(axis)
    _save(figure, output_directory / "numeric_bound_tree_edit.png")

    _plot_token_components(
        numeric,
        "m",
        "Numeric-bound canonical token edits: 8 → 6",
        output_directory / "numeric_bound_token_edits.png",
    )
