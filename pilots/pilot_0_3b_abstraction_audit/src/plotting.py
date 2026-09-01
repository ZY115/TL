"""Presentation-ready descriptive plots for the Pilot 0.3B audit."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPRESENTATIONS = ("core_tl", "macro_tl", "explicit", "parameterized")
COLORS = {
    "core_tl": "#2563EB",
    "macro_tl": "#7C3AED",
    "explicit": "#D97706",
    "parameterized": "#16803A",
}
LABELS = {
    "core_tl": "Core TL",
    "macro_tl": "Macro TL",
    "explicit": "Explicit monitor",
    "parameterized": "Parameterized DSL",
}


def _style(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)


def _save(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, metadata={"Creator": "pilot_0_3b"})
    plt.close(figure)


def _representation_lines(axis: plt.Axes, frame: pd.DataFrame, x: str, y: str) -> None:
    for representation in REPRESENTATIONS:
        subset = frame[frame["representation"] == representation]
        axis.plot(
            subset[x],
            subset[y],
            marker="o",
            color=COLORS[representation],
            label=LABELS[representation],
        )


def plot_all(
    construction_path: Path,
    summary_path: Path,
    stage_add_path: Path,
    rewire_path: Path,
    infrastructure_path: Path,
    output_directory: Path,
) -> None:
    construction = pd.read_csv(construction_path)
    summary = pd.read_csv(summary_path)
    stage_add = pd.read_csv(stage_add_path)
    rewire = pd.read_csv(rewire_path)
    infrastructure = pd.read_csv(infrastructure_path)

    figure, axis = plt.subplots(figsize=(8.6, 5.2))
    _representation_lines(axis, construction, "k", "tokens")
    axis.set(
        xlabel="Conditional stages k",
        ylabel="Author-facing lexical tokens",
        title="Author-facing task representation size",
    )
    axis.legend(frameon=False)
    _style(axis)
    _save(figure, output_directory / "author_facing_tokens.png")

    figure, axis = plt.subplots(figsize=(8.6, 5.2))
    ratio = construction[construction["k"] >= 1]
    _representation_lines(axis, ratio, "k", "surface_expansion_ratio")
    axis.set(
        xlabel="Conditional stages k",
        ylabel="Tokens / semantic payload field",
        title="Surface expansion ratio",
    )
    axis.legend(frameon=False)
    _style(axis)
    _save(figure, output_directory / "surface_expansion_ratio.png")

    figure, axis = plt.subplots(figsize=(8.6, 5.2))
    axis.plot(
        summary["k"],
        summary["macro_tl_tokens"],
        marker="o",
        color=COLORS["macro_tl"],
        label="Macro-TL surface",
    )
    axis.plot(
        summary["k"],
        summary["macro_tl_expanded_tokens"],
        marker="s",
        linestyle="--",
        color=COLORS["core_tl"],
        label="Expanded Core TL",
    )
    axis.set(
        xlabel="Conditional stages k",
        ylabel="Lexical tokens",
        title="Macro-TL surface and its exact expansion",
    )
    axis.legend(frameon=False)
    _style(axis)
    _save(figure, output_directory / "macro_surface_vs_expanded.png")

    for frame, x, title, filename in (
        (
            stage_add,
            "k_before",
            "Author-facing token edits when adding one stage",
            "stage_add_token_edits.png",
        ),
        (
            rewire,
            "k",
            "Author-facing token edits for Pq to Xq",
            "branch_rewire_token_edits.png",
        ),
    ):
        frame = frame.copy()
        frame["token_edit_total"] = (
            frame["tokens_inserted"] + frame["tokens_deleted"] + frame["tokens_changed"]
        )
        figure, axis = plt.subplots(figsize=(8.6, 5.2))
        if frame["token_edit_total"].nunique() == 1:
            value = frame["token_edit_total"].iloc[0]
            axis.text(
                0.5,
                0.5,
                f"All representations\n{value:g} token edit at every k",
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=13,
                color="#5B6472",
            )
            axis.set_ylim(value - 0.5, value + 0.5)
            axis.set_xlim(frame[x].min(), frame[x].max())
        else:
            _representation_lines(axis, frame, x, "token_edit_total")
        axis.set(xlabel=x, ylabel="Inserted + deleted + changed tokens", title=title)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(handles, labels, frameon=False)
        _style(axis)
        _save(figure, output_directory / filename)

    macro_tokens = infrastructure[
        infrastructure["abstraction_introduction_cost"] == "yes"
    ]["tokens"].sum()
    parameter_tokens = infrastructure[
        infrastructure["component"] == "Parameterized DSL parser/interpreter"
    ]["tokens"].sum()
    figure, axis = plt.subplots(figsize=(7.5, 5.0))
    bars = axis.bar(
        ["Macro-TL\nnew infrastructure", "Parameterized DSL\nparser/interpreter"],
        [macro_tokens, parameter_tokens],
        color=[COLORS["macro_tl"], COLORS["parameterized"]],
        width=0.58,
    )
    axis.bar_label(bars, fmt="%.0f")
    axis.set(
        ylabel="Reusable infrastructure lexical tokens",
        title="Descriptive infrastructure-size comparison",
    )
    axis.text(
        0.5,
        -0.18,
        "Different implementations; not a cross-language complexity score",
        transform=axis.transAxes,
        ha="center",
        color="#5B6472",
        fontsize=9,
    )
    _style(axis)
    _save(figure, output_directory / "infrastructure_descriptive_tokens.png")
