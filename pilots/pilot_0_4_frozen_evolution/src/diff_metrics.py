"""Deterministic task-source and infrastructure edit measurements."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from pathlib import Path

from .tree_diff import TreeNode, ordered_tree_edit_distance

TOKEN_PATTERN = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|->|:=|"
    r"[-+*/&|!<>=()\[\]{},.:]"
)


def lexical_tokens(source: str) -> list[str]:
    return TOKEN_PATTERN.findall(source)


def source_measurements(source: str) -> dict[str, int]:
    return {
        "characters": len(source),
        "lines": len(source.splitlines()),
        "tokens": len(lexical_tokens(source)),
    }


def python_ast_node_count(source: str) -> int:
    return sum(1 for _ in ast.walk(ast.parse(source)))


def python_syntax_tree(source: str) -> TreeNode:
    def convert(node: ast.AST) -> TreeNode:
        label = type(node).__name__
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            label += f":{node.name}"
        elif isinstance(node, ast.Name):
            label += f":{node.id}"
        elif isinstance(node, ast.arg):
            label += f":{node.arg}"
        elif isinstance(node, ast.Attribute):
            label += f":{node.attr}"
        elif isinstance(node, ast.Constant):
            label += f":{node.value!r}"
        return TreeNode(
            label, tuple(convert(child) for child in ast.iter_child_nodes(node))
        )

    return convert(ast.parse(source))


def _sequence_edit_counts(
    before: Sequence[str], after: Sequence[str]
) -> dict[str, int]:
    inserted = deleted = changed = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(
        a=before, b=after, autojunk=False
    ).get_opcodes():
        old_size, new_size = i2 - i1, j2 - j1
        if tag == "insert":
            inserted += new_size
        elif tag == "delete":
            deleted += old_size
        elif tag == "replace":
            paired = min(old_size, new_size)
            changed += paired
            deleted += old_size - paired
            inserted += new_size - paired
    return {"inserted": inserted, "deleted": deleted, "changed": changed}


def source_edit_measurements(before: str, after: str) -> dict[str, int]:
    lines = _sequence_edit_counts(before.splitlines(), after.splitlines())
    tokens = _sequence_edit_counts(lexical_tokens(before), lexical_tokens(after))
    return {
        "lines_inserted": lines["inserted"],
        "lines_deleted": lines["deleted"],
        "lines_changed": lines["changed"],
        "tokens_inserted": tokens["inserted"],
        "tokens_deleted": tokens["deleted"],
        "tokens_changed": tokens["changed"],
    }


def infrastructure_files(
    directory: Path, *, validation: bool = False
) -> dict[str, Path]:
    files = {}
    for path in sorted(directory.glob("*.py")):
        if path.name == "validation.py" and not validation:
            continue
        if path.name != "validation.py" and validation:
            continue
        files[path.name] = path
    return files


def directory_size(directory: Path, *, validation: bool = False) -> dict[str, int]:
    totals = {"characters": 0, "lines": 0, "tokens": 0, "python_ast_nodes": 0}
    for path in infrastructure_files(directory, validation=validation).values():
        source = path.read_text(encoding="utf-8")
        measured = source_measurements(source)
        for key in ("characters", "lines", "tokens"):
            totals[key] += measured[key]
        totals["python_ast_nodes"] += python_ast_node_count(source)
    return totals


def directory_edit(
    before_dir: Path, after_dir: Path, *, validation: bool = False
) -> dict[str, int]:
    before_files = infrastructure_files(before_dir, validation=validation)
    after_files = infrastructure_files(after_dir, validation=validation)
    names = sorted(before_files.keys() | after_files.keys())
    totals = {
        "files_added": 0,
        "files_deleted": 0,
        "files_modified": 0,
        "lines_inserted": 0,
        "lines_deleted": 0,
        "lines_changed": 0,
        "tokens_inserted": 0,
        "tokens_deleted": 0,
        "tokens_changed": 0,
        "ast_edit_distance_sum": 0,
    }
    for name in names:
        before = before_files.get(name)
        after = after_files.get(name)
        before_source = before.read_text(encoding="utf-8") if before else ""
        after_source = after.read_text(encoding="utf-8") if after else ""
        if before_source == after_source:
            continue
        if before is None:
            totals["files_added"] += 1
        elif after is None:
            totals["files_deleted"] += 1
        else:
            totals["files_modified"] += 1
        edits = source_edit_measurements(before_source, after_source)
        for key, value in edits.items():
            totals[key] += value
        if before_source and after_source:
            totals["ast_edit_distance_sum"] += ordered_tree_edit_distance(
                python_syntax_tree(before_source), python_syntax_tree(after_source)
            )
        elif before_source:
            totals["ast_edit_distance_sum"] += python_ast_node_count(before_source)
        elif after_source:
            totals["ast_edit_distance_sum"] += python_ast_node_count(after_source)
    return totals
