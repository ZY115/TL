"""Third-party-recomputable structural novelty metrics from Neutral IR alone."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields

from .schema import Expr, Expression, TaskSpec


def children(expr: Expression) -> tuple[Expression, ...]:
    result = []
    for field in fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, Expr):
            result.append(value)
        elif isinstance(value, tuple):
            result.extend(item for item in value if isinstance(item, Expr))
    return tuple(result)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class StructureSignature:
    edges: tuple[tuple[str, str], ...]
    paths: tuple[tuple[str, ...], ...]
    max_nesting_depth: int
    node_count: int
    scope_nesting_depth: int
    alternative_arities: tuple[int, ...]


def structure_signature(task: TaskSpec) -> StructureSignature:
    edges: list[tuple[str, str]] = []
    paths: list[tuple[str, ...]] = []
    alternative_arities: list[int] = []
    max_depth = scope_depth = nodes = 0

    def visit(
        expr: Expression, ancestry: tuple[str, ...], depth: int, scopes: int
    ) -> None:
        nonlocal max_depth, scope_depth, nodes
        name = type(expr).__name__
        nodes += 1
        max_depth = max(max_depth, depth)
        current_scopes = scopes + int(name in {"On", "MaintainUntil"})
        scope_depth = max(scope_depth, current_scopes)
        lineage = (*ancestry, name)
        for length in range(1, min(3, len(lineage)) + 1):
            paths.append(lineage[-length:])
        descendants = children(expr)
        if name in {"Alternative", "Priority"}:
            alternative_arities.append(len(descendants))
        for child in descendants:
            edges.append((name, type(child).__name__))
            visit(child, lineage, depth + 1, current_scopes)

    for requirement in task.requirements:
        visit(requirement.expr, (), 1, 0)
    return StructureSignature(
        tuple(sorted(edges)),
        tuple(sorted(paths)),
        max_depth,
        nodes,
        scope_depth,
        tuple(sorted(alternative_arities)),
    )


def unseen_composition_count(task: TaskSpec, training: tuple[TaskSpec, ...]) -> int:
    task_signature = structure_signature(task)
    train_edges: set[tuple[str, str]] = set()
    train_paths: set[tuple[str, ...]] = set()
    for train_task in training:
        signature = structure_signature(train_task)
        train_edges.update(signature.edges)
        train_paths.update(signature.paths)
    return len(
        (set(task_signature.edges) | set(task_signature.paths))
        - (train_edges | train_paths)  # type: ignore[operator]
    )


def signature_to_dict(signature: StructureSignature) -> dict[str, object]:
    return {
        "typed_parent_child_edges": [list(edge) for edge in signature.edges],
        "root_to_leaf_type_paths_length_le_3": [list(path) for path in signature.paths],
        "max_nesting_depth": signature.max_nesting_depth,
        "node_count": signature.node_count,
        "scope_nesting_depth": signature.scope_nesting_depth,
        "alternative_arity_multiset": list(signature.alternative_arities),
    }
