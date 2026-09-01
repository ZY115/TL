"""Normalized ordered trees and unit-cost APTED distance."""

from __future__ import annotations

from dataclasses import dataclass

from apted import APTED, Config


@dataclass(frozen=True, slots=True)
class TreeNode:
    label: str
    children: tuple["TreeNode", ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "children": [child.to_dict() for child in self.children],
        }


class UnitCostConfig(Config):
    def children(self, node: TreeNode) -> tuple[TreeNode, ...]:
        return node.children

    def insert(self, _node: TreeNode) -> int:
        return 1

    def delete(self, _node: TreeNode) -> int:
        return 1

    def rename(self, node1: TreeNode, node2: TreeNode) -> int:
        return 0 if node1.label == node2.label else 1


def ordered_tree_edit_distance(before: TreeNode, after: TreeNode) -> int:
    return int(APTED(before, after, UnitCostConfig()).compute_edit_distance())
