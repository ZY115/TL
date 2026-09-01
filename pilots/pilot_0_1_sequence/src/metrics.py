"""Deterministic source, AST, and edit-footprint measurements."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from difflib import SequenceMatcher

TOKEN_PATTERN = re.compile(
    r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|"""
    r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|->|:=|"
    r"[-+*/&|<>=()\[\]{},.:]"
)


def lexical_tokens(source: str) -> list[str]:
    """Apply one language-neutral deterministic tokenizer to all sources."""

    return TOKEN_PATTERN.findall(source)


def source_measurements(source: str) -> dict[str, int]:
    """Count exact characters, physical lines, and lexical tokens."""

    return {
        "characters": len(source),
        "lines": len(source.splitlines()),
        "tokens": len(lexical_tokens(source)),
    }


def python_ast_node_count(source: str) -> int:
    """Count Python parser AST nodes as raw within-language data."""

    return sum(1 for _node in ast.walk(ast.parse(source)))


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
        else:  # pragma: no cover - SequenceMatcher has four documented tags.
            raise AssertionError(f"Unexpected diff opcode: {tag}")

    return {"inserted": inserted, "deleted": deleted, "changed": changed}


def source_edit_measurements(before: str, after: str) -> dict[str, int]:
    """Measure canonical line and lexical-token edit components."""

    line_counts = _sequence_edit_counts(before.splitlines(), after.splitlines())
    token_counts = _sequence_edit_counts(lexical_tokens(before), lexical_tokens(after))
    return {
        "source_lines_inserted": line_counts["inserted"],
        "source_lines_deleted": line_counts["deleted"],
        "source_lines_changed": line_counts["changed"],
        "tokens_inserted": token_counts["inserted"],
        "tokens_deleted": token_counts["deleted"],
        "tokens_changed": token_counts["changed"],
    }
