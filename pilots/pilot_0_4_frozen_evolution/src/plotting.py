"""Eight pre-registered descriptive plots for Pilot 0.4."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SYSTEMS = ("general_tl_stack", "specialized_handwritten_dsl")
COLORS = {"general_tl_stack": "#2563EB", "specialized_handwritten_dsl": "#D97706"}
LABELS = {
    "general_tl_stack": "General TL stack",
    "specialized_handwritten_dsl": "Specialized DSL",
}


def _style(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E5E7EB", linewidth=0.8)


def _save(figure: plt.Figure, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, metadata={"Creator": "pilot_0_4"})
    plt.close(figure)


def _lines(axis: plt.Axes, frame: pd.DataFrame, y: str) -> None:
    for system in SYSTEMS:
        subset = frame[frame["system"] == system]
        axis.plot(
            subset["step"],
            subset[y],
            marker="o",
            color=COLORS[system],
            label=LABELS[system],
        )


def _line_plot(
    frame: pd.DataFrame, y: str, title: str, ylabel: str, path: Path
) -> None:
    figure, axis = plt.subplots(figsize=(8.6, 5.2))
    _lines(axis, frame, y)
    axis.set(xlabel="Evolution step", ylabel=ylabel, title=title)
    axis.legend(frameon=False)
    _style(axis)
    _save(figure, path)


def plot_all(results: Path, output: Path) -> None:
    task_sizes = pd.read_csv(results / "task_source_sizes.csv")
    task_edits = pd.read_csv(results / "task_edits.csv")
    infra_edits = pd.read_csv(results / "infrastructure_edits.csv")
    infra_sizes = pd.read_csv(results / "infrastructure_sizes.csv")
    cumulative = pd.read_csv(results / "cumulative.csv")
    evolution = pd.read_csv(results / "evolution_steps.csv")

    _line_plot(
        task_sizes,
        "tokens",
        "Current author-facing task-source size",
        "Lexical tokens",
        output / "01_task_source_tokens.png",
    )
    _line_plot(
        task_edits.rename(columns={"step_after": "step"}),
        "token_churn",
        "Per-step task-source lexical edit volume",
        "Inserted + deleted + changed tokens",
        output / "02_task_token_churn.png",
    )
    _line_plot(
        infra_edits.rename(columns={"step_after": "step"}),
        "token_churn",
        "Per-step infrastructure lexical edit volume",
        "Inserted + deleted + changed tokens",
        output / "03_infrastructure_token_churn.png",
    )
    _line_plot(
        cumulative,
        "cumulative_infrastructure_token_churn",
        "Cumulative infrastructure evolution",
        "Cumulative lexical edit volume",
        output / "04_cumulative_infrastructure_churn.png",
    )
    _line_plot(
        cumulative,
        "cumulative_task_token_churn",
        "Cumulative task-source evolution",
        "Cumulative lexical edit volume",
        output / "05_cumulative_task_churn.png",
    )
    _line_plot(
        infra_sizes,
        "tokens",
        "Current representation-system infrastructure size",
        "Lexical tokens",
        output / "06_current_infrastructure_size.png",
    )
    touched = infra_edits.rename(columns={"step_after": "step"}).copy()
    touched["files_touched"] = (
        touched["files_added"] + touched["files_deleted"] + touched["files_modified"]
    )
    _line_plot(
        touched,
        "files_touched",
        "Infrastructure files touched per evolution step",
        "Files added, deleted, or modified",
        output / "07_infrastructure_files_touched.png",
    )

    categorical = []
    for row in evolution[evolution["step"] != "E0"].to_dict("records"):
        for system, field in (
            ("general_tl_stack", "tl_infrastructure_changed"),
            ("specialized_handwritten_dsl", "dsl_infrastructure_changed"),
        ):
            categorical.append(
                {
                    "step": row["step"],
                    "system": system,
                    "extended": str(row[field]).lower() == "true",
                }
            )
    frame = pd.DataFrame(categorical)
    figure, axis = plt.subplots(figsize=(9.2, 4.8))
    for y, system in enumerate(SYSTEMS):
        subset = frame[frame["system"] == system]
        for _, row in subset.iterrows():
            axis.scatter(
                row["step"],
                y,
                s=180,
                marker="s",
                color="#B91C1C" if row["extended"] else "#16803A",
            )
    axis.set_yticks(range(len(SYSTEMS)), [LABELS[system] for system in SYSTEMS])
    axis.set(
        xlabel="Requirement evolution step",
        title="Source-only adaptation (green) vs infrastructure extension (red)",
    )
    axis.set_ylim(-0.6, 1.6)
    _style(axis)
    _save(figure, output / "08_capability_adaptation_mode.png")
