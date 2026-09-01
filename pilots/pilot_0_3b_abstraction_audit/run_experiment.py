#!/usr/bin/env python3
"""Run Pilot 0.3B: abstraction-level fairness audit."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence, Set
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("Pilot 0.3B requires Python 3.11 or newer")

from src.core_tl.evaluator import evaluate as evaluate_core_tl
from src.core_tl.generator import formula_tree, task_formula
from src.core_tl.syntax import Formula, pretty_task, structural_counts
from src.explicit.generator import (
    compile_monitor,
    explicit_structural_metrics,
    explicit_tree,
    generate_source,
)
from src.macro_tl.expander import expand_macro_tl
from src.macro_tl.formatter import format_macro_tl
from src.macro_tl.parser import parse_macro_tl
from src.macro_tl.syntax import (
    MacroTask,
    macro_structural_metrics,
    macro_task,
    surface_tree as macro_surface_tree,
)
from src.metrics import (
    python_ast_node_count,
    python_syntax_tree,
    source_edit_measurements,
    source_measurements,
    task_value_occurrences,
    tree_measurements,
)
from src.model import Stage, stages_for_k, with_left_goal_rewired
from src.oracle import branch_timing_oracle
from src.parameterized.monitor import (
    canonical_parameter_source,
    evaluate_parameterized,
    parameter_structural_metrics,
    parameter_tree,
    parse_parameter_source,
)
from src.plotting import plot_all
from src.trace_model import task_alphabet, validate_trace_model
from src.traces import (
    branch_rewire_probe_traces,
    deterministic_groups,
    flattened_deterministic_traces,
    structured_random_traces,
)
from src.tree_diff import TreeNode, ordered_tree_edit_distance

ROOT = Path(__file__).resolve().parent
PILOT_03 = ROOT.parent / "pilot_0_3_branch_timing"
GENERATED = ROOT / "generated"
RESULTS = ROOT / "results"
PLOTS = ROOT / "plots"
REPRESENTATIONS = ("core_tl", "macro_tl", "explicit", "parameterized")
BASE_RANDOM_SEED = 20_260_901
RANDOM_TRACES_PER_K = 10_000

CONSTRUCTION_COLUMNS = [
    "k",
    "representation",
    "characters",
    "lines",
    "tokens",
    "semantic_payload_fields",
    "task_value_occurrences",
    "surface_expansion_ratio",
    "tokens_per_stage",
    "surface_ast_nodes",
    "surface_ast_depth",
    "expanded_tokens",
    "macro_compression_ratio",
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
    "macro_invocations",
    "macro_timed_choice_stage_count",
    "macro_ordered_choices_count",
    "macro_arguments",
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

SUMMARY_COLUMNS = [
    "k",
    "core_tl_tokens",
    "macro_tl_tokens",
    "macro_tl_expanded_tokens",
    "explicit_tokens",
    "parameterized_tokens",
    "semantic_payload_fields",
    "core_tl_tokens_per_stage",
    "macro_tl_tokens_per_stage",
    "explicit_tokens_per_stage",
    "parameterized_tokens_per_stage",
    "core_tl_surface_expansion_ratio",
    "macro_tl_surface_expansion_ratio",
    "explicit_surface_expansion_ratio",
    "parameterized_surface_expansion_ratio",
    "macro_compression_ratio",
]

SEMANTICS_COLUMNS = [
    "k",
    "variant",
    "test_type",
    "num_trajectories",
    "core_tl_matches",
    "core_tl_mismatches",
    "macro_tl_matches",
    "macro_tl_mismatches",
    "explicit_matches",
    "explicit_mismatches",
    "parameterized_matches",
    "parameterized_mismatches",
    "macro_core_ast_equal",
    "random_seed",
]

STAGE_ADD_COLUMNS = [
    "k_before",
    "k_after",
    "representation",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "tree_edit_distance",
    "semantic_payload_fields_added",
    "task_value_occurrences_added",
    "surface_tree_edit_distance",
    "expanded_core_tree_edit_distance",
    "surface_tokens_changed",
    "expanded_tokens_inserted",
    "expanded_tokens_deleted",
    "expanded_tokens_changed",
]

REWIRE_COLUMNS = [
    "k",
    "modified_stage",
    "old_goal",
    "new_goal",
    "representation",
    "lines_inserted",
    "lines_deleted",
    "lines_changed",
    "tokens_inserted",
    "tokens_deleted",
    "tokens_changed",
    "tree_edit_distance",
    "task_values_changed",
    "surface_tree_edit_distance",
    "expanded_core_tree_edit_distance",
    "surface_tokens_changed",
    "expanded_tokens_inserted",
    "expanded_tokens_deleted",
    "expanded_tokens_changed",
]

INFRASTRUCTURE_COLUMNS = [
    "component",
    "category",
    "abstraction_introduction_cost",
    "characters",
    "lines",
    "tokens",
    "python_ast_nodes",
]

REFACTOR_COLUMNS = [
    "k",
    "definition_before",
    "definition_after",
    "infrastructure_lines_inserted",
    "infrastructure_lines_deleted",
    "infrastructure_lines_changed",
    "infrastructure_tokens_inserted",
    "infrastructure_tokens_deleted",
    "infrastructure_tokens_changed",
    "infrastructure_python_ast_edit_distance",
    "task_source_tokens_changed",
    "task_source_tree_edit_distance",
    "expanded_core_tokens_changed",
    "expanded_core_tree_edit_distance",
    "expanded_ast_equal",
]

FAIRNESS_COLUMNS = [
    "representation",
    "author_facing_abstraction",
    "reusable_interpreter_or_expander",
    "task_specific_information_location",
    "task_specific_information_counted",
    "environment_assumptions_externalized",
]


def _reset_output_directories() -> None:
    for directory in (GENERATED, RESULTS, PLOTS):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)


def _tree_json(tree: TreeNode) -> str:
    return json.dumps(tree.to_dict(), indent=2, sort_keys=True) + "\n"


def _build_task(stages: Sequence[Stage]) -> dict[str, dict[str, object]]:
    canonical_stages = tuple(stages)
    direct_formula = task_formula(canonical_stages)
    core_source = pretty_task(direct_formula)

    surface_task = macro_task(canonical_stages)
    macro_source = format_macro_tl(surface_task)
    parsed_macro = parse_macro_tl(macro_source)
    if parsed_macro != surface_task:
        raise AssertionError("Macro-TL source did not round-trip")
    expanded_v1 = expand_macro_tl(parsed_macro, definition_version=1)
    expanded_v2 = expand_macro_tl(parsed_macro, definition_version=2)
    if expanded_v1 != direct_formula or expanded_v2 != direct_formula:
        raise AssertionError("Macro expansion is not the canonical Core-TL AST")

    explicit_source = generate_source(canonical_stages)
    parameter_source = canonical_parameter_source(canonical_stages)
    parsed_parameter = parse_parameter_source(parameter_source)
    if parsed_parameter != canonical_stages:
        raise AssertionError("Parameterized schema did not round-trip")

    return {
        "core_tl": {
            "source": core_source,
            "tree": formula_tree(direct_formula),
            "formula": direct_formula,
        },
        "macro_tl": {
            "source": macro_source,
            "tree": macro_surface_tree(parsed_macro),
            "task": parsed_macro,
            "formula": expanded_v1,
            "formula_v2": expanded_v2,
            "expanded_source": pretty_task(expanded_v1),
            "expanded_tree": formula_tree(expanded_v1),
        },
        "explicit": {
            "source": explicit_source,
            "tree": explicit_tree(canonical_stages),
            "monitor": compile_monitor(explicit_source),
        },
        "parameterized": {
            "source": parameter_source,
            "tree": parameter_tree(parsed_parameter),
            "stages": parsed_parameter,
        },
    }


def _assert_frozen_base(k: int, representations: dict[str, dict[str, object]]) -> None:
    reference = PILOT_03 / "generated" / f"B{k}" / "base"
    core_reference = (reference / "formula.btl").read_text(encoding="utf-8")
    parameter_reference = (reference / "task_config.py").read_text(encoding="utf-8")
    if representations["core_tl"]["source"] != core_reference:
        raise AssertionError(f"B{k} Core TL changed from Pilot 0.3")
    if representations["parameterized"]["source"] != parameter_reference:
        raise AssertionError(f"B{k} parameterized schema changed from Pilot 0.3")


def _write_generated_variant(
    k: int, variant: str, representations: dict[str, dict[str, object]]
) -> None:
    directory = GENERATED / f"B{k}" / variant
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "core_tl": "core_tl_formula.btl",
        "macro_tl": "macro_tl_surface.mtl",
        "explicit": "explicit_monitor.py",
        "parameterized": "parameterized_config.py",
    }
    for representation, filename in files.items():
        source = representations[representation]["source"]
        tree = representations[representation]["tree"]
        assert isinstance(source, str) and isinstance(tree, TreeNode)
        (directory / filename).write_text(source, encoding="utf-8")
        (directory / f"{representation}_surface_tree.json").write_text(
            _tree_json(tree), encoding="utf-8"
        )
    macro = representations["macro_tl"]
    expanded_source = macro["expanded_source"]
    expanded_tree = macro["expanded_tree"]
    assert isinstance(expanded_source, str) and isinstance(expanded_tree, TreeNode)
    (directory / "macro_tl_expanded_core.btl").write_text(
        expanded_source, encoding="utf-8"
    )
    (directory / "macro_tl_expanded_core_tree.json").write_text(
        _tree_json(expanded_tree), encoding="utf-8"
    )


def _semantic_row(
    *,
    k: int,
    variant: str,
    test_type: str,
    traces: Iterable[Sequence[str]],
    stages: Sequence[Stage],
    alphabet: Set[str],
    representations: dict[str, dict[str, object]],
    random_seed: int | str = "",
) -> dict[str, int | str | bool]:
    core_formula = representations["core_tl"]["formula"]
    macro_formula = representations["macro_tl"]["formula"]
    explicit_monitor = representations["explicit"]["monitor"]
    parameter_stages = representations["parameterized"]["stages"]
    assert isinstance(core_formula, Formula) and isinstance(macro_formula, Formula)
    assert callable(explicit_monitor) and isinstance(parameter_stages, tuple)
    ast_equal = core_formula == macro_formula

    counts = {
        "num_trajectories": 0,
        "core_tl_matches": 0,
        "core_tl_mismatches": 0,
        "macro_tl_matches": 0,
        "macro_tl_mismatches": 0,
        "explicit_matches": 0,
        "explicit_mismatches": 0,
        "parameterized_matches": 0,
        "parameterized_mismatches": 0,
    }
    for trajectory in traces:
        if not validate_trace_model(trajectory, alphabet):
            raise AssertionError(f"Generated trace violates shared model: {trajectory}")
        expected = branch_timing_oracle(trajectory, stages)
        values = {
            "core_tl": evaluate_core_tl(core_formula, trajectory),
            "macro_tl": evaluate_core_tl(macro_formula, trajectory),
            "explicit": bool(explicit_monitor(trajectory)),
            "parameterized": evaluate_parameterized(trajectory, parameter_stages),
        }
        counts["num_trajectories"] += 1
        for representation, value in values.items():
            suffix = "matches" if value == expected else "mismatches"
            counts[f"{representation}_{suffix}"] += 1
    return {
        "k": k,
        "variant": variant,
        "test_type": test_type,
        **counts,
        "macro_core_ast_equal": ast_equal,
        "random_seed": random_seed,
    }


def _ratio(numerator: int, denominator: int) -> float | str:
    return round(numerator / denominator, 6) if denominator else ""


def _construction_rows(
    k: int,
    stages: Sequence[Stage],
    representations: dict[str, dict[str, object]],
    token_baselines: dict[str, int],
) -> list[dict[str, object]]:
    rows = []
    payload = 6 * k
    for representation in REPRESENTATIONS:
        source = representations[representation]["source"]
        tree = representations[representation]["tree"]
        assert isinstance(source, str) and isinstance(tree, TreeNode)
        measurements = source_measurements(source)
        row: dict[str, object] = {column: "" for column in CONSTRUCTION_COLUMNS}
        row.update(
            {
                "k": k,
                "representation": representation,
                **measurements,
                "semantic_payload_fields": payload,
                "task_value_occurrences": task_value_occurrences(source, stages),
                "surface_expansion_ratio": _ratio(measurements["tokens"], payload),
                "tokens_per_stage": (
                    round(
                        (measurements["tokens"] - token_baselines[representation]) / k,
                        6,
                    )
                    if k
                    else ""
                ),
                **tree_measurements(tree),
            }
        )
        if representation == "core_tl":
            row.update(structural_counts(representations[representation]["formula"]))
            row.update(
                {
                    "tl_decision_stages": k,
                    "tl_branch_clauses": 4 * k,
                    "tl_bounded_obligations": 2 * k,
                }
            )
        elif representation == "macro_tl":
            macro = representations[representation]
            expanded_source = macro["expanded_source"]
            task = macro["task"]
            assert isinstance(expanded_source, str) and isinstance(task, MacroTask)
            expanded_tokens = source_measurements(expanded_source)["tokens"]
            row.update(macro_structural_metrics(task))
            row.update(
                {
                    "expanded_tokens": expanded_tokens,
                    "macro_compression_ratio": _ratio(
                        expanded_tokens, measurements["tokens"]
                    ),
                }
            )
        elif representation == "explicit":
            row.update(explicit_structural_metrics(source, stages))
        else:
            row.update(parameter_structural_metrics(stages))
        rows.append(row)
    return rows


def _summary_rows(
    construction_rows: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    lookup = {
        (int(row["k"]), str(row["representation"])): row for row in construction_rows
    }
    rows = []
    for k in range(7):
        core = lookup[(k, "core_tl")]
        macro = lookup[(k, "macro_tl")]
        explicit = lookup[(k, "explicit")]
        parameter = lookup[(k, "parameterized")]
        rows.append(
            {
                "k": k,
                "core_tl_tokens": core["tokens"],
                "macro_tl_tokens": macro["tokens"],
                "macro_tl_expanded_tokens": macro["expanded_tokens"],
                "explicit_tokens": explicit["tokens"],
                "parameterized_tokens": parameter["tokens"],
                "semantic_payload_fields": 6 * k,
                "core_tl_tokens_per_stage": core["tokens_per_stage"],
                "macro_tl_tokens_per_stage": macro["tokens_per_stage"],
                "explicit_tokens_per_stage": explicit["tokens_per_stage"],
                "parameterized_tokens_per_stage": parameter["tokens_per_stage"],
                "core_tl_surface_expansion_ratio": core["surface_expansion_ratio"],
                "macro_tl_surface_expansion_ratio": macro["surface_expansion_ratio"],
                "explicit_surface_expansion_ratio": explicit["surface_expansion_ratio"],
                "parameterized_surface_expansion_ratio": parameter[
                    "surface_expansion_ratio"
                ],
                "macro_compression_ratio": macro["macro_compression_ratio"],
            }
        )
    return rows


def _common_edit(before: dict[str, object], after: dict[str, object]) -> dict[str, int]:
    before_source = before["source"]
    after_source = after["source"]
    before_tree = before["tree"]
    after_tree = after["tree"]
    assert isinstance(before_source, str) and isinstance(after_source, str)
    assert isinstance(before_tree, TreeNode) and isinstance(after_tree, TreeNode)
    return {
        **source_edit_measurements(before_source, after_source),
        "tree_edit_distance": ordered_tree_edit_distance(before_tree, after_tree),
    }


def _expanded_macro_edit(
    before: dict[str, object], after: dict[str, object]
) -> dict[str, int]:
    before_source = before["expanded_source"]
    after_source = after["expanded_source"]
    before_tree = before["expanded_tree"]
    after_tree = after["expanded_tree"]
    assert isinstance(before_source, str) and isinstance(after_source, str)
    assert isinstance(before_tree, TreeNode) and isinstance(after_tree, TreeNode)
    source_edits = source_edit_measurements(before_source, after_source)
    return {
        "expanded_core_tree_edit_distance": ordered_tree_edit_distance(
            before_tree, after_tree
        ),
        "expanded_tokens_inserted": source_edits["tokens_inserted"],
        "expanded_tokens_deleted": source_edits["tokens_deleted"],
        "expanded_tokens_changed": source_edits["tokens_changed"],
    }


def _stage_add_rows(
    k: int,
    before_stages: Sequence[Stage],
    after_stages: Sequence[Stage],
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for representation in REPRESENTATIONS:
        common = _common_edit(before[representation], after[representation])
        before_source = before[representation]["source"]
        after_source = after[representation]["source"]
        assert isinstance(before_source, str) and isinstance(after_source, str)
        row: dict[str, object] = {column: "" for column in STAGE_ADD_COLUMNS}
        row.update(
            {
                "k_before": k,
                "k_after": k + 1,
                "representation": representation,
                **common,
                "semantic_payload_fields_added": 6,
                "task_value_occurrences_added": task_value_occurrences(
                    after_source, after_stages
                )
                - task_value_occurrences(before_source, before_stages),
            }
        )
        if representation == "macro_tl":
            row.update(
                {
                    "surface_tree_edit_distance": common["tree_edit_distance"],
                    "surface_tokens_changed": common["tokens_changed"],
                    **_expanded_macro_edit(
                        before[representation], after[representation]
                    ),
                }
            )
        rows.append(row)
    return rows


def _rewire_rows(
    k: int,
    q: int,
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for representation in REPRESENTATIONS:
        common = _common_edit(before[representation], after[representation])
        row: dict[str, object] = {column: "" for column in REWIRE_COLUMNS}
        row.update(
            {
                "k": k,
                "modified_stage": q,
                "old_goal": f"P{q}",
                "new_goal": f"X{q}",
                "representation": representation,
                **common,
                "task_values_changed": 1,
            }
        )
        if representation == "macro_tl":
            row.update(
                {
                    "surface_tree_edit_distance": common["tree_edit_distance"],
                    "surface_tokens_changed": common["tokens_changed"],
                    **_expanded_macro_edit(
                        before[representation], after[representation]
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


def _infrastructure_rows() -> list[dict[str, object]]:
    components = [
        (
            "Core TL syntax/evaluator",
            "core_tl",
            "no",
            [ROOT / "src/core_tl/syntax.py", ROOT / "src/core_tl/evaluator.py"],
        ),
        (
            "Core TL generator",
            "core_tl",
            "no",
            [ROOT / "src/core_tl/generator.py"],
        ),
        (
            "Macro TL syntax/parser",
            "macro_tl",
            "yes",
            [ROOT / "src/macro_tl/syntax.py", ROOT / "src/macro_tl/parser.py"],
        ),
        (
            "Macro TL expander",
            "macro_tl",
            "yes",
            [ROOT / "src/macro_tl/expander.py"],
        ),
        (
            "Macro TL formatter",
            "macro_tl",
            "yes",
            [ROOT / "src/macro_tl/formatter.py"],
        ),
        (
            "Macro definitions V1",
            "macro_tl",
            "yes",
            [ROOT / "src/macro_tl/definitions_v1.py"],
        ),
        (
            "Macro definitions V2 refactor",
            "macro_tl",
            "no",
            [ROOT / "src/macro_tl/definitions_v2.py"],
        ),
        (
            "Explicit generator/compiler",
            "explicit",
            "no",
            [ROOT / "src/explicit/generator.py"],
        ),
        (
            "Parameterized DSL parser/interpreter",
            "parameterized",
            "no",
            [ROOT / "src/parameterized/monitor.py"],
        ),
        ("Oracle", "shared", "no", [ROOT / "src/oracle.py"]),
        (
            "Shared trace validator",
            "shared",
            "no",
            [ROOT / "src/trace_model.py"],
        ),
        (
            "Shared test generators",
            "shared",
            "no",
            [ROOT / "src/traces.py"],
        ),
    ]
    rows = []
    for component, category, introduction, paths in components:
        measurements = {"characters": 0, "lines": 0, "tokens": 0}
        ast_nodes = 0
        for path in paths:
            source = path.read_text(encoding="utf-8")
            values = source_measurements(source)
            for key in measurements:
                measurements[key] += values[key]
            ast_nodes += python_ast_node_count(source)
        rows.append(
            {
                "component": component,
                "category": category,
                "abstraction_introduction_cost": introduction,
                **measurements,
                "python_ast_nodes": ast_nodes,
            }
        )
    return rows


def _macro_refactor_rows(
    base_tasks: dict[int, dict[str, dict[str, object]]],
) -> list[dict[str, object]]:
    v1_source = (ROOT / "src/macro_tl/definitions_v1.py").read_text(encoding="utf-8")
    v2_source = (ROOT / "src/macro_tl/definitions_v2.py").read_text(encoding="utf-8")
    edits = source_edit_measurements(v1_source, v2_source)
    infrastructure_tree_distance = ordered_tree_edit_distance(
        python_syntax_tree(v1_source), python_syntax_tree(v2_source)
    )
    rows = []
    for k in range(7):
        macro = base_tasks[k]["macro_tl"]
        formula_v1 = macro["formula"]
        formula_v2 = macro["formula_v2"]
        source = macro["source"]
        surface = macro["tree"]
        assert isinstance(formula_v1, Formula) and isinstance(formula_v2, Formula)
        assert isinstance(source, str) and isinstance(surface, TreeNode)
        rows.append(
            {
                "k": k,
                "definition_before": "V1 direct four-clause expansion",
                "definition_after": "V2 helper-macro composition",
                "infrastructure_lines_inserted": edits["lines_inserted"],
                "infrastructure_lines_deleted": edits["lines_deleted"],
                "infrastructure_lines_changed": edits["lines_changed"],
                "infrastructure_tokens_inserted": edits["tokens_inserted"],
                "infrastructure_tokens_deleted": edits["tokens_deleted"],
                "infrastructure_tokens_changed": edits["tokens_changed"],
                "infrastructure_python_ast_edit_distance": infrastructure_tree_distance,
                "task_source_tokens_changed": 0,
                "task_source_tree_edit_distance": 0,
                "expanded_core_tokens_changed": 0,
                "expanded_core_tree_edit_distance": 0,
                "expanded_ast_equal": formula_v1 == formula_v2,
            }
        )
    return rows


def _fairness_rows() -> list[dict[str, str]]:
    return [
        {
            "representation": "Core TL",
            "author_facing_abstraction": "primitive temporal operators",
            "reusable_interpreter_or_expander": "Core-TL evaluator",
            "task_specific_information_location": "formula",
            "task_specific_information_counted": "yes",
            "environment_assumptions_externalized": "yes",
        },
        {
            "representation": "Macro TL",
            "author_facing_abstraction": "TIMED_CHOICE_STAGE and ORDERED_CHOICES",
            "reusable_interpreter_or_expander": "macro expander plus Core-TL evaluator",
            "task_specific_information_location": "macro calls",
            "task_specific_information_counted": "yes",
            "environment_assumptions_externalized": "yes",
        },
        {
            "representation": "Explicit monitor",
            "author_facing_abstraction": "direct state and branch logic",
            "reusable_interpreter_or_expander": "Python runtime",
            "task_specific_information_location": "generated task monitor",
            "task_specific_information_counted": "yes",
            "environment_assumptions_externalized": "yes",
        },
        {
            "representation": "Parameterized DSL",
            "author_facing_abstraction": "six-field stage descriptor",
            "reusable_interpreter_or_expander": "generic stage interpreter",
            "task_specific_information_location": "STAGES list",
            "task_specific_information_counted": "yes",
            "environment_assumptions_externalized": "yes",
        },
    ]


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_metadata() -> None:
    package_names = ["apted", "black", "matplotlib", "pandas", "pytest"]
    pilot03_construction = PILOT_03 / "results/construction.csv"
    metadata = {
        "pilot": "0.3B",
        "source_pilot": "0.3",
        "source_pilot_commit_sha": _git_commit(),
        "source_pilot_construction_sha256": hashlib.sha256(
            pilot03_construction.read_bytes()
        ).hexdigest(),
        "task_semantics_unchanged": True,
        "macro_expansion_target": "Pilot 0.3 Core TL",
        "parameterized_schema_frozen": True,
        "environment_trace_validation_shared": True,
        "semantic_payload_fields_per_stage": 6,
        "semantic_payload_fixed_information": ["S", "E", "stage ordering"],
        "surface_expansion_ratio_denominator": "6*k; undefined at k=0",
        "random_seed_base": BASE_RANDOM_SEED,
        "random_seed_rule": "base + k",
        "random_traces_per_k": RANDOM_TRACES_PER_K,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in package_names},
        "tree_edit": "APTED ordered tree edit distance; unit insert/delete/rename",
        "source_diff": "SequenceMatcher autojunk=False",
        "k6_full_reverse_expected": False,
        "k6_successful_non_stage_goal_order": [6, 5, 4, 1, 2, 3],
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
    base_tasks: dict[int, dict[str, dict[str, object]]] = {}
    semantics_rows: list[dict[str, object]] = []

    for k in range(7):
        stages = stages_for_k(k)
        task = _build_task(stages)
        _assert_frozen_base(k, task)
        base_tasks[k] = task
        _write_generated_variant(k, "base", task)
        alphabet = task_alphabet(stages)
        for test_type, traces in deterministic_groups(stages).items():
            semantics_rows.append(
                _semantic_row(
                    k=k,
                    variant="base",
                    test_type=test_type,
                    traces=traces,
                    stages=stages,
                    alphabet=alphabet,
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
                    alphabet=alphabet,
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
                raise AssertionError("Stage-add task is not canonical B(k+1)")
        semantics_rows.append(
            _semantic_row(
                k=k + 1,
                variant=f"stage_add_B{k + 1}",
                test_type="modified_stage_add",
                traces=flattened_deterministic_traces(stages),
                stages=stages,
                alphabet=task_alphabet(stages),
                representations=modified,
            )
        )

    rewire_tasks: dict[
        int, tuple[int, tuple[Stage, ...], dict[str, dict[str, object]]]
    ] = {}
    for k in range(1, 7):
        original_stages = stages_for_k(k)
        q = (k + 1) // 2
        modified_stages = with_left_goal_rewired(original_stages, q)
        modified = _build_task(modified_stages)
        rewire_tasks[k] = (q, modified_stages, modified)
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
                alphabet=task_alphabet(modified_stages, additional_events=(f"P{q}",)),
                representations=modified,
            )
        )

    mismatch_total = sum(
        int(row[column])
        for row in semantics_rows
        for column in (
            "core_tl_mismatches",
            "macro_tl_mismatches",
            "explicit_mismatches",
            "parameterized_mismatches",
        )
    )
    if mismatch_total or not all(row["macro_core_ast_equal"] for row in semantics_rows):
        _write_csv(RESULTS / "semantics.csv", SEMANTICS_COLUMNS, semantics_rows)
        raise AssertionError("Semantic or Macro/Core AST validation failed")

    token_baselines = {
        representation: source_measurements(
            base_tasks[0][representation]["source"]  # type: ignore[arg-type]
        )["tokens"]
        for representation in REPRESENTATIONS
    }
    construction_rows = [
        row
        for k in range(7)
        for row in _construction_rows(
            k, stages_for_k(k), base_tasks[k], token_baselines
        )
    ]
    summary_rows = _summary_rows(construction_rows)
    stage_add_rows = [
        row
        for k in range(6)
        for row in _stage_add_rows(
            k,
            stages_for_k(k),
            stages_for_k(k + 1),
            base_tasks[k],
            stage_add_tasks[k],
        )
    ]
    rewire_rows = [
        row
        for k in range(1, 7)
        for row in _rewire_rows(
            k, rewire_tasks[k][0], base_tasks[k], rewire_tasks[k][2]
        )
    ]
    infrastructure_rows = _infrastructure_rows()
    refactor_rows = _macro_refactor_rows(base_tasks)
    if not all(row["expanded_ast_equal"] for row in refactor_rows):
        raise AssertionError("Macro-definition refactor changed expanded semantics")

    result_specs = [
        ("construction.csv", CONSTRUCTION_COLUMNS, construction_rows),
        ("abstraction_summary.csv", SUMMARY_COLUMNS, summary_rows),
        ("semantics.csv", SEMANTICS_COLUMNS, semantics_rows),
        ("stage_add_edit.csv", STAGE_ADD_COLUMNS, stage_add_rows),
        ("branch_rewire_edit.csv", REWIRE_COLUMNS, rewire_rows),
        ("infrastructure.csv", INFRASTRUCTURE_COLUMNS, infrastructure_rows),
        (
            "macro_infrastructure_refactor.csv",
            REFACTOR_COLUMNS,
            refactor_rows,
        ),
        ("baseline_fairness.csv", FAIRNESS_COLUMNS, _fairness_rows()),
    ]
    result_paths = []
    for filename, columns, rows in result_specs:
        path = RESULTS / filename
        _write_csv(path, columns, rows)
        result_paths.append(path)
    _write_metadata()
    result_paths.append(RESULTS / "metadata.json")
    _write_checksums(result_paths)

    plot_all(
        RESULTS / "construction.csv",
        RESULTS / "abstraction_summary.csv",
        RESULTS / "stage_add_edit.csv",
        RESULTS / "branch_rewire_edit.csv",
        RESULTS / "infrastructure.csv",
        PLOTS,
    )
    evaluations = sum(int(row["num_trajectories"]) for row in semantics_rows)
    print(f"Pilot 0.3B complete: {evaluations:,} traces evaluated per representation")
    print("All four representations match the oracle; all Macro/Core AST checks pass")


if __name__ == "__main__":
    main()
