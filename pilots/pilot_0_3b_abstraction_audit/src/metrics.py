"""Pilot-compatible deterministic source and edit metrics."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from .model import Stage
from .tree_diff import TreeNode

TOKEN_PATTERN = re.compile(
    r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|"""
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
    return sum(1 for _node in ast.walk(ast.parse(source)))


def _token_value(token: str) -> str:
    if token.startswith(('"', "'")):
        value = ast.literal_eval(token)
        return str(value)
    return token


def task_value_occurrences(source: str, stages: Sequence[Stage]) -> int:
    """Count exact occurrences of the six stage payload values."""

    payload_values = {str(field) for stage in stages for field in stage.fields()}
    normalized_tokens = [_token_value(token) for token in lexical_tokens(source)]
    return sum(token in payload_values for token in normalized_tokens)


def tree_measurements(tree: TreeNode) -> dict[str, int]:
    def walk(node: TreeNode, depth: int) -> tuple[int, int]:
        child_results = [walk(child, depth + 1) for child in node.children]
        count = 1 + sum(result[0] for result in child_results)
        maximum = max([depth, *(result[1] for result in child_results)])
        return count, maximum

    nodes, depth = walk(tree, 1)
    return {"surface_ast_nodes": nodes, "surface_ast_depth": depth}


def python_syntax_tree(source: str) -> TreeNode:
    """Create a deterministic Python AST tree for infrastructure-only edits."""

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
    inserted = 0
    deleted = 0
    changed = 0
    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_size = i2 - i1
        new_size = j2 - j1
        if tag == "equal":
            continue
        if tag == "insert":
            inserted += new_size
        elif tag == "delete":
            deleted += old_size
        elif tag == "replace":
            paired = min(old_size, new_size)
            changed += paired
            deleted += old_size - paired
            inserted += new_size - paired
        else:  # pragma: no cover
            raise AssertionError(f"Unexpected diff opcode: {tag}")
    return {"inserted": inserted, "deleted": deleted, "changed": changed}


def source_edit_measurements(before: str, after: str) -> dict[str, int]:
    line_counts = _sequence_edit_counts(before.splitlines(), after.splitlines())
    token_counts = _sequence_edit_counts(lexical_tokens(before), lexical_tokens(after))
    return {
        "lines_inserted": line_counts["inserted"],
        "lines_deleted": line_counts["deleted"],
        "lines_changed": line_counts["changed"],
        "tokens_inserted": token_counts["inserted"],
        "tokens_deleted": token_counts["deleted"],
        "tokens_changed": token_counts["changed"],
    }
