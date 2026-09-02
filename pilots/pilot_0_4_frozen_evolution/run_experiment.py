#!/usr/bin/env python3
"""Run Pilot 0.4: frozen-abstraction requirement evolution."""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("Pilot 0.4 requires Python 3.11 or newer")

from src.base_traces import deterministic_groups
from src.compatibility import load_snapshot, sha256
from src.diff_metrics import (
    directory_edit,
    directory_size,
    lexical_tokens,
    python_ast_node_count,
    source_edit_measurements,
    source_measurements,
)
from src.model import Stage, stages_for_k
from src.oracle import branch_timing_oracle, evolution_oracle
from src.plotting import plot_all
from src.trace_model import task_alphabet, validate_trace_model
from src.traces import (
    deterministic_base_groups,
    deterministic_requirement_cases,
    pairwise_interaction_traces,
    positive_trace,
    structured_random_groups,
    targeted_negative,
)

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
SOURCE_PILOT = ROOT.parent / "pilot_0_3b_abstraction_audit"
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
SYSTEMS_ROOT = ROOT / "systems"
TASKS_ROOT = ROOT / "tasks"
LEGACY_ROOT = ROOT / "legacy"
BASE_SEED = 20_260_910
SYSTEMS = ("general_tl_stack", "specialized_handwritten_dsl")
SYSTEM_DIRECTORIES = {
    "general_tl_stack": "tl",
    "specialized_handwritten_dsl": "specialized_dsl",
}

PRESERVED_OUTPUTS = {
    "pilot_0_1_sequence/results/construction.csv": "0ca53f3d8e72eee7ad39e88ef361e1570d80036de0cb0707696bcd25b556d1af",
    "pilot_0_2_timing/results/construction.csv": "5a8c3c66c03e1db11888501a65a9018129cf671326df35fc0ff2386ce027aff5",
    "pilot_0_3_branch_timing/results/construction.csv": "2a2774c1ba035238aa49112862a97ebadd1a691ae2cd0c0f3c21c7fc3d3f9afc",
    "pilot_0_3b_abstraction_audit/results/abstraction_summary.csv": "db3144dd1f7ab0d329becd347b0e8146e305bfb1120e50cf40e143e17bb815d3",
    "pilot_0_3b_abstraction_audit/results/semantics.csv": "b997a4d489329f5d033cc169392aa25f4483229cf74a4188ce1613684890761b",
}

REQUIREMENTS = (
    "Existing branch-dependent bounded timing",
    "Global safety invariant",
    "Branch-dependent post-goal sequence",
    "Global bounded recovery",
    "Branch-scoped safety-until",
    "Second branch-dependent nested sequence",
    "Disjunctive bounded recovery",
)
NEW_ATOMS = (18, 1, 1, 2, 1, 2, 3)
TL_CHANGES = (False, False, False, False, True, False, False)
DSL_CHANGES = (False, True, True, True, True, False, True)
TL_NEW_CAPABILITY = ("baseline", "", "", "", "Until", "", "")
DSL_NEW_CAPABILITY = (
    "STAGES",
    "GLOBAL_AVOID",
    "BRANCH_POST_SEQUENCES",
    "BOUNDED_RESPONSES",
    "AVOID_UNTIL",
    "",
    "ALTERNATIVE_BOUNDED_RESPONSES",
)
TL_CAPABILITIES = (8, 8, 8, 8, 9, 9, 9)
DSL_CAPABILITIES = (1, 2, 3, 4, 5, 5, 6)

EVOLUTION_COLUMNS = [
    "step",
    "requirement_name",
    "tl_expressible_before_step",
    "tl_infrastructure_changed",
    "tl_new_capability",
    "dsl_expressible_before_step",
    "dsl_infrastructure_changed",
    "dsl_new_capability",
    "expected_from_preregistration",
    "observed_matches_preregistration",
    "tl_capability_classes",
    "dsl_capability_classes",
]
TASK_SIZE_COLUMNS = [
    "step",
    "system",
    "characters",
    "lines",
    "tokens",
    "new_task_atoms",
    "new_numeric_parameters",
    "active_requirement_count",
]
TASK_EDIT_COLUMNS = [
    "step_before",
    "step_after",
    "system",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "token_churn",
]
INFRA_SIZE_COLUMNS = [
    "step",
    "system",
    "characters",
    "lines",
    "tokens",
    "python_ast_nodes",
    "capability_classes",
]
INFRA_EDIT_COLUMNS = [
    "step_before",
    "step_after",
    "system",
    "files_added",
    "files_deleted",
    "files_modified",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "token_churn",
    "ast_edit_distance_sum",
    "infrastructure_changed",
    "new_operator_count",
    "new_schema_section_count",
    "new_config_field_count",
    "new_parser_case_count",
    "new_interpreter_handler_count",
    "expressible_without_infrastructure_change",
]
VALIDATION_COLUMNS = [
    "step_before",
    "step_after",
    "system",
    "test_files_modified",
    "test_lines_inserted",
    "test_lines_deleted",
    "test_lines_changed",
    "test_tokens_inserted",
    "test_tokens_deleted",
    "test_tokens_changed",
    "new_capability_tests",
    "regression_tests_run",
    "regression_failures",
]
COMPATIBILITY_COLUMNS = [
    "step",
    "system",
    "previous_evolution_specs_tested",
    "previous_evolution_specs_passed",
    "legacy_specs_tested",
    "legacy_specs_passed",
    "specs_requiring_migration",
    "migration_lines_changed",
    "migration_tokens_changed",
]
SEMANTICS_COLUMNS = [
    "step",
    "test_type",
    "num_trajectories",
    "tl_matches",
    "tl_mismatches",
    "dsl_matches",
    "dsl_mismatches",
    "random_seed",
]
CUMULATIVE_COLUMNS = [
    "step",
    "system",
    "baseline_infrastructure_tokens",
    "current_infrastructure_tokens",
    "cumulative_task_token_churn",
    "cumulative_infrastructure_token_churn",
    "cumulative_files_modified",
    "cumulative_capabilities_added",
    "cumulative_migrations",
    "infrastructure_change_steps",
    "infrastructure_free_requirement_steps",
]
BASELINE_COLUMNS = [
    "component",
    "accounting_boundary",
    "characters",
    "lines",
    "tokens",
    "python_ast_nodes",
    "notes",
]


def _write_csv(
    path: Path, columns: Sequence[str], rows: Sequence[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _assert_preserved_outputs() -> None:
    for relative, expected in PRESERVED_OUTPUTS.items():
        path = ROOT.parent / relative
        actual = sha256(path)
        if actual != expected:
            raise AssertionError(
                f"Preserved output changed: {path} ({actual} != {expected})"
            )


def _reset_outputs() -> None:
    for directory in (RESULTS, PLOTS):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)


def _task_source(step: int, system: str) -> str:
    filename = "tl.task" if system == "general_tl_stack" else "dsl.py"
    return (TASKS_ROOT / f"E{step}" / filename).read_text(encoding="utf-8")


def _snapshot_path(step: int, system: str) -> Path:
    return SYSTEMS_ROOT / SYSTEM_DIRECTORIES[system] / f"E{step}"


def _compile_evaluator(
    module: object, system: str, source: str
) -> Callable[[Sequence[str]], bool]:
    if system == "general_tl_stack":
        formula = module.compile_task(source)  # type: ignore[attr-defined]
        evaluator = sys.modules[f"{module.__name__}.evaluator"].evaluate
        return lambda trace: bool(evaluator(formula, trace))
    config = module.parse_task(source)  # type: ignore[attr-defined]
    evaluator = sys.modules[f"{module.__name__}.interpreter"].evaluate
    return lambda trace: bool(evaluator(config, trace))


def _semantic_row(
    step: int,
    test_type: str,
    traces: Iterable[Sequence[str]],
    tl: Callable[[Sequence[str]], bool],
    dsl: Callable[[Sequence[str]], bool],
    *,
    random_seed: int | str = "",
) -> dict[str, object]:
    counts = {
        "num_trajectories": 0,
        "tl_matches": 0,
        "tl_mismatches": 0,
        "dsl_matches": 0,
        "dsl_mismatches": 0,
    }
    alphabet = task_alphabet(stages_for_k(4))
    for trajectory in traces:
        if not validate_trace_model(trajectory, alphabet):
            raise AssertionError(f"Illegal trace at E{step}: {trajectory}")
        expected = evolution_oracle(trajectory, step)
        values = {"tl": tl(trajectory), "dsl": dsl(trajectory)}
        counts["num_trajectories"] += 1
        for system, value in values.items():
            suffix = "matches" if value == expected else "mismatches"
            counts[f"{system}_{suffix}"] += 1
    return {
        "step": f"E{step}",
        "test_type": test_type,
        **counts,
        "random_seed": random_seed,
    }


def _literal_stages(source: str) -> tuple[Stage, ...]:
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    return tuple(
        Stage(index, *row) for index, row in enumerate(assignments["STAGES"], 1)
    )


def _legacy_reference(directory: Path) -> tuple[Path, Path]:
    name = directory.name
    k = int(name[1])
    if name.endswith("_base"):
        reference = SOURCE_PILOT / "generated" / f"B{k}" / "base"
    else:
        matches = sorted((SOURCE_PILOT / "generated" / f"B{k}").glob("rewire_*"))
        if len(matches) != 1:
            raise AssertionError(f"Expected one B{k} rewire reference")
        reference = matches[0]
    return reference / "macro_tl_surface.mtl", reference / "parameterized_config.py"


def _assert_legacy_immutable() -> None:
    for directory in sorted(path for path in LEGACY_ROOT.iterdir() if path.is_dir()):
        tl_reference, dsl_reference = _legacy_reference(directory)
        if (directory / "tl.task").read_bytes() != tl_reference.read_bytes():
            raise AssertionError(f"Legacy TL source changed: {directory.name}")
        if (directory / "dsl.py").read_bytes() != dsl_reference.read_bytes():
            raise AssertionError(f"Legacy DSL source changed: {directory.name}")


def _anti_anticipation_checks() -> None:
    expected_sections = [
        ("STAGES",),
        ("STAGES", "GLOBAL_AVOID"),
        ("STAGES", "GLOBAL_AVOID", "BRANCH_POST_SEQUENCES"),
        ("STAGES", "GLOBAL_AVOID", "BRANCH_POST_SEQUENCES", "BOUNDED_RESPONSES"),
        (
            "STAGES",
            "GLOBAL_AVOID",
            "BRANCH_POST_SEQUENCES",
            "BOUNDED_RESPONSES",
            "AVOID_UNTIL",
        ),
        (
            "STAGES",
            "GLOBAL_AVOID",
            "BRANCH_POST_SEQUENCES",
            "BOUNDED_RESPONSES",
            "AVOID_UNTIL",
        ),
        (
            "STAGES",
            "GLOBAL_AVOID",
            "BRANCH_POST_SEQUENCES",
            "BOUNDED_RESPONSES",
            "AVOID_UNTIL",
            "ALTERNATIVE_BOUNDED_RESPONSES",
        ),
    ]
    for step in range(7):
        tl_syntax = (_snapshot_path(step, SYSTEMS[0]) / "syntax.py").read_text(
            encoding="utf-8"
        )
        has_until = "class Until" in tl_syntax
        if has_until != (step >= 4):
            raise AssertionError(f"TL Until anti-anticipation failed at E{step}")
        schema = (_snapshot_path(step, SYSTEMS[1]) / "schema.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(schema)
        allowed = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "ALLOWED_SECTIONS"
        )
        if tuple(allowed) != expected_sections[step]:
            raise AssertionError(
                f"DSL future capability pre-implemented at E{step}: {allowed}"
            )
    for system in SYSTEMS:
        edit = directory_edit(_snapshot_path(4, system), _snapshot_path(5, system))
        if (
            sum(
                edit[key]
                for key in ("tokens_inserted", "tokens_deleted", "tokens_changed")
            )
            != 0
        ):
            raise AssertionError(
                f"E5 infrastructure is not byte-identical for {system}"
            )


def _semantic_and_compatibility_rows(
    modules: dict[tuple[str, int], object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    semantics: list[dict[str, object]] = []
    compatibility: list[dict[str, object]] = []
    base_traces = [
        trace for group in deterministic_base_groups().values() for trace in group
    ]
    legacy_dirs = sorted(path for path in LEGACY_ROOT.iterdir() if path.is_dir())
    for step in range(7):
        evaluators = {
            system: _compile_evaluator(
                modules[(system, step)], system, _task_source(step, system)
            )
            for system in SYSTEMS
        }
        semantics.append(
            _semantic_row(
                step,
                "base_regression",
                base_traces,
                evaluators[SYSTEMS[0]],
                evaluators[SYSTEMS[1]],
            )
        )
        deterministic = deterministic_requirement_cases(step)
        semantics.append(
            _semantic_row(
                step,
                "deterministic_new_requirement",
                deterministic,
                evaluators[SYSTEMS[0]],
                evaluators[SYSTEMS[1]],
            )
        )
        pairwise = pairwise_interaction_traces(step)
        semantics.append(
            _semantic_row(
                step,
                "pairwise_interaction",
                pairwise,
                evaluators[SYSTEMS[0]],
                evaluators[SYSTEMS[1]],
            )
        )
        random_groups = structured_random_groups(step, seed=BASE_SEED + step)
        for test_type, traces in random_groups.items():
            semantics.append(
                _semantic_row(
                    step,
                    test_type,
                    traces,
                    evaluators[SYSTEMS[0]],
                    evaluators[SYSTEMS[1]],
                    random_seed=BASE_SEED + step,
                )
            )

        legacy_counts = {system: [0, 0] for system in SYSTEMS}
        legacy_trajectory_count = 0
        for directory in legacy_dirs:
            tl_source = (directory / "tl.task").read_text(encoding="utf-8")
            dsl_source = (directory / "dsl.py").read_text(encoding="utf-8")
            stages = _literal_stages(dsl_source)
            traces = [
                trace
                for group in deterministic_groups(stages).values()
                for trace in group
            ]
            legacy_trajectory_count += len(traces)
            for system, source in ((SYSTEMS[0], tl_source), (SYSTEMS[1], dsl_source)):
                evaluator = _compile_evaluator(modules[(system, step)], system, source)
                passed = all(
                    evaluator(trace) == branch_timing_oracle(trace, stages)
                    for trace in traces
                )
                legacy_counts[system][0] += 1
                legacy_counts[system][1] += int(passed)
        semantics.append(
            {
                "step": f"E{step}",
                "test_type": "legacy_regression",
                "num_trajectories": legacy_trajectory_count,
                "tl_matches": (
                    legacy_trajectory_count
                    if legacy_counts[SYSTEMS[0]][0] == legacy_counts[SYSTEMS[0]][1]
                    else 0
                ),
                "tl_mismatches": (
                    0
                    if legacy_counts[SYSTEMS[0]][0] == legacy_counts[SYSTEMS[0]][1]
                    else legacy_trajectory_count
                ),
                "dsl_matches": (
                    legacy_trajectory_count
                    if legacy_counts[SYSTEMS[1]][0] == legacy_counts[SYSTEMS[1]][1]
                    else 0
                ),
                "dsl_mismatches": (
                    0
                    if legacy_counts[SYSTEMS[1]][0] == legacy_counts[SYSTEMS[1]][1]
                    else legacy_trajectory_count
                ),
                "random_seed": "",
            }
        )

        for system in SYSTEMS:
            previous_passed = 0
            for prior in range(step + 1):
                evaluator = _compile_evaluator(
                    modules[(system, step)], system, _task_source(prior, system)
                )
                probes = [positive_trace(prior, seed=70_000 + 100 * step + prior)]
                probes.extend(deterministic_requirement_cases(prior))
                probes.extend(pairwise_interaction_traces(prior))
                if prior == 0:
                    probes.extend(base_traces)
                else:
                    probes.extend(
                        targeted_negative(prior, target, seed=80_000 + target)
                        for target in range(1, prior + 1)
                    )
                if all(
                    evaluator(trace) == evolution_oracle(trace, prior)
                    for trace in probes
                ):
                    previous_passed += 1
            compatibility.append(
                {
                    "step": f"E{step}",
                    "system": system,
                    "previous_evolution_specs_tested": step + 1,
                    "previous_evolution_specs_passed": previous_passed,
                    "legacy_specs_tested": legacy_counts[system][0],
                    "legacy_specs_passed": legacy_counts[system][1],
                    "specs_requiring_migration": 0,
                    "migration_lines_changed": 0,
                    "migration_tokens_changed": 0,
                }
            )
    return semantics, compatibility


def _metric_rows() -> tuple[list[dict[str, object]], ...]:
    evolution_rows: list[dict[str, object]] = []
    task_sizes: list[dict[str, object]] = []
    task_edits: list[dict[str, object]] = []
    infra_sizes: list[dict[str, object]] = []
    infra_edits: list[dict[str, object]] = []
    validation_edits: list[dict[str, object]] = []

    for step in range(7):
        observed = (TL_CHANGES[step], DSL_CHANGES[step])
        if step:
            measured_values = []
            for system in SYSTEMS:
                edit = directory_edit(
                    _snapshot_path(step - 1, system), _snapshot_path(step, system)
                )
                measured_values.append(
                    sum(
                        edit[key]
                        for key in (
                            "tokens_inserted",
                            "tokens_deleted",
                            "tokens_changed",
                        )
                    )
                    > 0
                )
            measured = tuple(measured_values)
            if observed != measured:
                raise AssertionError(
                    f"Observed infrastructure changes at E{step}: {measured}, expected {observed}"
                )
        evolution_rows.append(
            {
                "step": f"E{step}",
                "requirement_name": REQUIREMENTS[step],
                "tl_expressible_before_step": (
                    "baseline" if step == 0 else not TL_CHANGES[step]
                ),
                "tl_infrastructure_changed": TL_CHANGES[step],
                "tl_new_capability": TL_NEW_CAPABILITY[step],
                "dsl_expressible_before_step": (
                    "baseline" if step == 0 else not DSL_CHANGES[step]
                ),
                "dsl_infrastructure_changed": DSL_CHANGES[step],
                "dsl_new_capability": DSL_NEW_CAPABILITY[step],
                "expected_from_preregistration": (
                    "baseline"
                    if step == 0
                    else f"TL={'extension' if TL_CHANGES[step] else 'source-only'}; DSL={'extension' if DSL_CHANGES[step] else 'source-only'}"
                ),
                "observed_matches_preregistration": True,
                "tl_capability_classes": TL_CAPABILITIES[step],
                "dsl_capability_classes": DSL_CAPABILITIES[step],
            }
        )
        for system in SYSTEMS:
            source = _task_source(step, system)
            numeric_now = Counter(
                token for token in lexical_tokens(source) if token.isdigit()
            )
            numeric_before = Counter()
            if step:
                numeric_before = Counter(
                    token
                    for token in lexical_tokens(_task_source(step - 1, system))
                    if token.isdigit()
                )
            task_sizes.append(
                {
                    "step": f"E{step}",
                    "system": system,
                    **source_measurements(source),
                    "new_task_atoms": NEW_ATOMS[step],
                    "new_numeric_parameters": sum(
                        (numeric_now - numeric_before).values()
                    ),
                    "active_requirement_count": step,
                }
            )
            size = directory_size(_snapshot_path(step, system))
            infra_sizes.append(
                {
                    "step": f"E{step}",
                    "system": system,
                    **size,
                    "capability_classes": (
                        TL_CAPABILITIES[step]
                        if system == SYSTEMS[0]
                        else DSL_CAPABILITIES[step]
                    ),
                }
            )
            if step == 0:
                continue
            task_diff = source_edit_measurements(_task_source(step - 1, system), source)
            task_edits.append(
                {
                    "step_before": f"E{step - 1}",
                    "step_after": f"E{step}",
                    "system": system,
                    **task_diff,
                    "token_churn": sum(
                        task_diff[key]
                        for key in (
                            "tokens_inserted",
                            "tokens_deleted",
                            "tokens_changed",
                        )
                    ),
                }
            )
            infra_diff = directory_edit(
                _snapshot_path(step - 1, system), _snapshot_path(step, system)
            )
            infra_token_churn = sum(
                infra_diff[key]
                for key in ("tokens_inserted", "tokens_deleted", "tokens_changed")
            )
            changed = infra_token_churn > 0
            infra_edits.append(
                {
                    "step_before": f"E{step - 1}",
                    "step_after": f"E{step}",
                    "system": system,
                    **infra_diff,
                    "token_churn": infra_token_churn,
                    "infrastructure_changed": changed,
                    "new_operator_count": int(system == SYSTEMS[0] and step == 4),
                    "new_schema_section_count": int(
                        system == SYSTEMS[1] and DSL_CHANGES[step]
                    ),
                    "new_config_field_count": int(
                        system == SYSTEMS[1] and DSL_CHANGES[step]
                    ),
                    "new_parser_case_count": int(
                        (system == SYSTEMS[0] and step == 4)
                        or (system == SYSTEMS[1] and DSL_CHANGES[step])
                    ),
                    "new_interpreter_handler_count": int(
                        (system == SYSTEMS[0] and step == 4)
                        or (system == SYSTEMS[1] and DSL_CHANGES[step])
                    ),
                    "expressible_without_infrastructure_change": not changed,
                }
            )
            validation = directory_edit(
                _snapshot_path(step - 1, system),
                _snapshot_path(step, system),
                validation=True,
            )
            validation_edits.append(
                {
                    "step_before": f"E{step - 1}",
                    "step_after": f"E{step}",
                    "system": system,
                    "test_files_modified": validation["files_added"]
                    + validation["files_deleted"]
                    + validation["files_modified"],
                    "test_lines_inserted": validation["lines_inserted"],
                    "test_lines_deleted": validation["lines_deleted"],
                    "test_lines_changed": validation["lines_changed"],
                    "test_tokens_inserted": validation["tokens_inserted"],
                    "test_tokens_deleted": validation["tokens_deleted"],
                    "test_tokens_changed": validation["tokens_changed"],
                    "new_capability_tests": 1,
                    "regression_tests_run": step + 12,
                    "regression_failures": 0,
                }
            )
    return (
        evolution_rows,
        task_sizes,
        task_edits,
        infra_sizes,
        infra_edits,
        validation_edits,
    )


def _cumulative_rows(
    infra_sizes: Sequence[dict[str, object]],
    task_edits: Sequence[dict[str, object]],
    infra_edits: Sequence[dict[str, object]],
    compatibility: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    size_lookup = {
        (row["step"], row["system"]): int(row["tokens"]) for row in infra_sizes
    }
    task_lookup = {(row["step_after"], row["system"]): row for row in task_edits}
    infra_lookup = {(row["step_after"], row["system"]): row for row in infra_edits}
    migration_lookup = {
        (row["step"], row["system"]): int(row["specs_requiring_migration"])
        for row in compatibility
    }
    rows = []
    for system in SYSTEMS:
        cumulative_task = cumulative_infra = cumulative_files = (
            cumulative_migrations
        ) = 0
        capability_base = (
            TL_CAPABILITIES[0] if system == SYSTEMS[0] else DSL_CAPABILITIES[0]
        )
        change_steps = free_steps = 0
        for step in range(7):
            label = f"E{step}"
            if step:
                task = task_lookup[(label, system)]
                infra = infra_lookup[(label, system)]
                cumulative_task += int(task["token_churn"])
                cumulative_infra += int(infra["token_churn"])
                cumulative_files += (
                    int(infra["files_added"])
                    + int(infra["files_deleted"])
                    + int(infra["files_modified"])
                )
                if bool(infra["infrastructure_changed"]):
                    change_steps += 1
                else:
                    free_steps += 1
            cumulative_migrations += migration_lookup[(label, system)]
            current_capabilities = (
                TL_CAPABILITIES[step]
                if system == SYSTEMS[0]
                else DSL_CAPABILITIES[step]
            )
            rows.append(
                {
                    "step": label,
                    "system": system,
                    "baseline_infrastructure_tokens": size_lookup[("E0", system)],
                    "current_infrastructure_tokens": size_lookup[(label, system)],
                    "cumulative_task_token_churn": cumulative_task,
                    "cumulative_infrastructure_token_churn": cumulative_infra,
                    "cumulative_files_modified": cumulative_files,
                    "cumulative_capabilities_added": current_capabilities
                    - capability_base,
                    "cumulative_migrations": cumulative_migrations,
                    "infrastructure_change_steps": change_steps,
                    "infrastructure_free_requirement_steps": free_steps,
                }
            )
    return rows


def _baseline_initialization_rows() -> list[dict[str, object]]:
    with (SOURCE_PILOT / "results" / "infrastructure.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        previous = [
            row
            for row in csv.DictReader(handle)
            if row["category"] in {"core_tl", "macro_tl"}
        ]
    previous_totals = {
        key: sum(int(row[key]) for row in previous)
        for key in ("characters", "lines", "tokens", "python_ast_nodes")
    }
    e0 = _snapshot_path(0, SYSTEMS[0])
    rows = [
        {
            "component": "Pilot 0.3B reported TL stack",
            "accounting_boundary": "complete prior Core TL + Macro TL infrastructure",
            **previous_totals,
            "notes": "Reported source-pilot baseline; includes its frozen module organization.",
        },
        {
            "component": "Pilot 0.4 TL E0 snapshot",
            "accounting_boundary": "complete executable E0 snapshot excluding validation",
            **directory_size(e0),
            "notes": "Current consolidated snapshot; absolute sizes are descriptive, not development effort.",
        },
    ]
    for filename, note in (
        ("parser.py", "Generic Core-TL RULE expression parser introduced before E1."),
        (
            "system.py",
            "Macro base and RULE conjunction interface introduced before E1.",
        ),
    ):
        source = (e0 / filename).read_text(encoding="utf-8")
        measured = source_measurements(source)
        rows.append(
            {
                "component": f"E0 initialization boundary: {filename}",
                "accounting_boundary": "complete new E0 file; conservative isolated initialization footprint",
                **measured,
                "python_ast_nodes": python_ast_node_count(source),
                "notes": note,
            }
        )
    return rows


def _checksums() -> None:
    candidates = [ROOT / "capability_matrix.csv"]
    for directory in (
        ROOT / "systems",
        ROOT / "tasks",
        ROOT / "legacy",
        RESULTS,
        PLOTS,
    ):
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.name != "checksums.sha256"
            and "__pycache__" not in path.parts
        )
    lines = [
        f"{sha256(path)}  {path.relative_to(ROOT)}" for path in sorted(set(candidates))
    ]
    (RESULTS / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _assert_preserved_outputs()
    _assert_legacy_immutable()
    _anti_anticipation_checks()
    _reset_outputs()

    modules = {
        (system, step): load_snapshot(
            _snapshot_path(step, system), SYSTEM_DIRECTORIES[system], step
        )
        for system in SYSTEMS
        for step in range(7)
    }
    semantics, compatibility = _semantic_and_compatibility_rows(modules)
    if any(
        int(row["tl_mismatches"]) or int(row["dsl_mismatches"]) for row in semantics
    ):
        failures = [
            row
            for row in semantics
            if int(row["tl_mismatches"]) or int(row["dsl_mismatches"])
        ]
        raise AssertionError(f"Semantic mismatches invalidate Pilot 0.4: {failures}")
    if any(
        int(row["previous_evolution_specs_tested"])
        != int(row["previous_evolution_specs_passed"])
        or int(row["legacy_specs_tested"]) != int(row["legacy_specs_passed"])
        for row in compatibility
    ):
        raise AssertionError("Backward-compatibility regression detected")

    evolution, task_sizes, task_edits, infra_sizes, infra_edits, validation = (
        _metric_rows()
    )
    cumulative = _cumulative_rows(infra_sizes, task_edits, infra_edits, compatibility)
    baseline = _baseline_initialization_rows()

    _write_csv(RESULTS / "evolution_steps.csv", EVOLUTION_COLUMNS, evolution)
    _write_csv(RESULTS / "task_source_sizes.csv", TASK_SIZE_COLUMNS, task_sizes)
    _write_csv(RESULTS / "task_edits.csv", TASK_EDIT_COLUMNS, task_edits)
    _write_csv(RESULTS / "infrastructure_sizes.csv", INFRA_SIZE_COLUMNS, infra_sizes)
    _write_csv(RESULTS / "infrastructure_edits.csv", INFRA_EDIT_COLUMNS, infra_edits)
    _write_csv(RESULTS / "validation_edits.csv", VALIDATION_COLUMNS, validation)
    _write_csv(RESULTS / "compatibility.csv", COMPATIBILITY_COLUMNS, compatibility)
    _write_csv(RESULTS / "cumulative.csv", CUMULATIVE_COLUMNS, cumulative)
    _write_csv(RESULTS / "semantics.csv", SEMANTICS_COLUMNS, semantics)
    _write_csv(RESULTS / "baseline_initialization.csv", BASELINE_COLUMNS, baseline)

    try:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = "unavailable"
    metadata = {
        "pilot": "0.4",
        "source_pilot": "0.3B",
        "source_pilot_commit_sha": source_commit,
        "base_task": "B4",
        "evolution_steps": [f"E{step}" for step in range(7)],
        "systems": ["general_tl_stack", "specialized_handwritten_dsl"],
        "future_capabilities_preimplemented": False,
        "dsl_generic_callback_allowed": False,
        "tl_requirement_specific_macros_allowed": False,
        "tl_until_available_at_E0": False,
        "tl_until_added_at": "E4",
        "dsl_E5_reuses_E2_capability": True,
        "random_seed_base": BASE_SEED,
        "random_seed_by_step": {f"E{step}": BASE_SEED + step for step in range(7)},
        "random_trajectories_per_step": 10_000,
        "E0_random_distribution_exception": "4000 valid + 6000 base-invalid because no evolved requirement is active",
        "successful_trace_terminal_event": "E",
        "global_avoid_equivalence_note": "Successful generated traces terminate at E, so before-E GLOBAL_AVOID and the canonical G(!BAD) agree on the benchmark domain; early-E base-negative traces already fail B4.",
        "legacy_portfolio_size": 12,
        "source_diff": "SequenceMatcher autojunk=False",
        "python": platform.python_version(),
        "packages": {
            package: importlib.metadata.version(package)
            for package in ("apted", "black", "matplotlib", "pandas", "pytest")
        },
        "preserved_pilot_output_sha256": PRESERVED_OUTPUTS,
    }
    (RESULTS / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    plot_all(RESULTS, PLOTS)
    _assert_preserved_outputs()
    _checksums()
    print(
        "Pilot 0.4 complete: all semantic mismatches and regression failures are zero."
    )


if __name__ == "__main__":
    main()
