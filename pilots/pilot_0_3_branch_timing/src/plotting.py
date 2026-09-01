"""Separate raw-metric plots for Pilot 0.3."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPRESENTATIONS = ("tl", "explicit_conditional", "parameterized")
COLORS = {
    "tl": "#2563EB",
    "explicit_conditional": "#D97706",
    "parameterized": "#16803A",
}
LABELS = {
    "tl": "Bounded TL",
    "explicit_conditional": "Explicit conditional monitor",
    "parameterized": "Parameterized monitor",
}


def _style(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)


def _save(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, metadata={"Creator": "pilot_0_3_branch_timing"})
    plt.close(figure)


def _representation_lines(
    axis: plt.Axes, frame: pd.DataFrame, x_column: str, y_column: str
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


def _token_components(
    frame: pd.DataFrame, x_column: str, title: str, path: Path
) -> None:
    columns = (
        ("tokens_inserted", "Inserted"),
        ("tokens_deleted", "Deleted"),
        ("tokens_changed", "Changed"),
    )
    figure, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharex=True)
    for axis, (column, label) in zip(axes, columns, strict=True):
        if frame[column].nunique() == 1:
            value = frame[column].iloc[0]
            axis.text(
                0.5,
                0.5,
                f"All representations\n{value:g} at every k",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#5B6472",
                fontsize=11,
            )
            axis.set_ylim(value - 0.5, value + 0.5)
            axis.set_xlim(frame[x_column].min(), frame[x_column].max())
        else:
            _representation_lines(axis, frame, x_column, column)
        axis.set(title=f"{label} tokens", xlabel=x_column, ylabel="Tokens")
        _style(axis)
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(handles, labels, frameon=False, fontsize=8)
    figure.suptitle(title)
    _save(figure, path)


def _structural_plot(
    frame: pd.DataFrame,
    metrics: Sequence[tuple[str, str]],
    title: str,
    path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(8, 5))
    for column, label in metrics:
        axis.plot(frame["k"], frame[column], marker="o", label=label)
    axis.set(xlabel="Conditional stages k", ylabel="Count", title=title)
    axis.legend(frameon=False, ncol=2, fontsize=8)
    _style(axis)
    _save(figure, path)


def plot_all(
    construction_path: Path,
    stage_add_path: Path,
    rewire_path: Path,
    output_directory: Path,
) -> None:
    construction = pd.read_csv(construction_path)
    stage_add = pd.read_csv(stage_add_path)
    rewire = pd.read_csv(rewire_path)

    for metric, ylabel, filename in (
        ("tokens", "Task-specific lexical tokens", "construction_tokens.png"),
        ("characters", "Task-specific characters", "construction_characters.png"),
    ):
        figure, axis = plt.subplots(figsize=(8, 5))
        _representation_lines(axis, construction, "k", metric)
        axis.set(
            xlabel="Conditional stages k",
            ylabel=ylabel,
            title=ylabel,
        )
        axis.legend(frameon=False)
        _style(axis)
        _save(figure, output_directory / filename)

    tl = construction[construction["representation"] == "tl"]
    _structural_plot(
        tl,
        (
            ("tl_ast_nodes", "AST nodes"),
            ("tl_atoms", "atoms"),
            ("tl_and", "and"),
            ("tl_eventually", "eventually"),
            ("tl_always", "always"),
            ("tl_bounded_eventually", "bounded eventually"),
        ),
        "Bounded-TL structural metrics",
        output_directory / "construction_tl_structural.png",
    )
    explicit = construction[construction["representation"] == "explicit_conditional"]
    _structural_plot(
        explicit,
        (
            ("explicit_variables", "variables"),
            ("explicit_decision_branches", "decision branches"),
            ("explicit_goal_branches", "goal branches"),
            ("explicit_conditions", "conditions"),
            ("explicit_deadline_checks", "deadline checks"),
        ),
        "Explicit-monitor structural metrics",
        output_directory / "construction_explicit_structural.png",
    )
    parameterized = construction[construction["representation"] == "parameterized"]
    _structural_plot(
        parameterized,
        (
            ("parameter_stage_count", "stages"),
            ("parameter_branch_count", "branches"),
            ("parameter_goal_mapping_count", "goal mappings"),
            ("parameter_bound_count", "bounds"),
            ("parameter_task_fields", "task fields"),
        ),
        "Parameterized-configuration structural metrics",
        output_directory / "construction_parameterized_structural.png",
    )

    figure, axis = plt.subplots(figsize=(8, 5))
    for representation in REPRESENTATIONS:
        subset = construction[
            construction["representation"] == representation
        ].sort_values("k")
        axis.plot(
            subset["k"].to_numpy()[:-1],
            subset["tokens"].to_numpy()[1:] - subset["tokens"].to_numpy()[:-1],
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )
    axis.set(
        xlabel="Stages before addition k",
        ylabel="Delta task-specific tokens",
        title="Marginal token increase when adding one stage",
    )
    axis.legend(frameon=False)
    _style(axis)
    _save(figure, output_directory / "construction_marginal_tokens.png")

    for frame, x_column, title, filename in (
        (
            stage_add,
            "k_before",
            "Stage-addition ordered tree edit distance",
            "stage_add_tree_edit.png",
        ),
        (
            rewire,
            "k",
            "Branch-rewire ordered tree edit distance",
            "branch_rewire_tree_edit.png",
        ),
    ):
        figure, axis = plt.subplots(figsize=(8, 5))
        if frame["tree_edit_distance"].nunique() == 1:
            value = frame["tree_edit_distance"].iloc[0]
            axis.text(
                0.5,
                0.5,
                f"All representations\n{value:g} at every k",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#5B6472",
                fontsize=13,
            )
            axis.set_ylim(value - 0.5, value + 0.5)
            axis.set_xlim(frame[x_column].min(), frame[x_column].max())
        else:
            _representation_lines(axis, frame, x_column, "tree_edit_distance")
        axis.set(
            xlabel=x_column,
            ylabel="Ordered tree edit distance",
            title=title,
        )
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(handles, labels, frameon=False)
        _style(axis)
        _save(figure, output_directory / filename)

    _token_components(
        stage_add,
        "k_before",
        "Stage-addition canonical token edits",
        output_directory / "stage_add_token_edits.png",
    )
    _token_components(
        rewire,
        "k",
        "Branch-rewire canonical token edits",
        output_directory / "branch_rewire_token_edits.png",
    )
