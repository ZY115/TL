"""Generate a reasonable explicit phase-state monitor with timestamp variables."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import black

from src.model import TimingConstraint
from src.tree_diff import TreeNode


def _wait_state(target: str) -> str:
    return f"WAIT_{target}"


def _destination(targets: Sequence[str], index: int) -> str:
    if index + 1 == len(targets):
        return "SUCCESS"
    return _wait_state(targets[index + 1])


def generate_source(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> str:
    """Return one self-contained Black-formatted explicit monitor."""

    if not targets:
        raise ValueError("Pilot 0.2 requires a non-empty sequence")

    starts = {constraint.start: constraint for constraint in timing_constraints}
    ends = {constraint.end: constraint for constraint in timing_constraints}
    lines = ["def monitor(trajectory):", f'    state = "{_wait_state(targets[0])}"']
    for constraint in timing_constraints:
        lines.append(f"    start_{constraint.name} = None")
    lines.extend(["    for step, event in enumerate(trajectory):"])

    for index, target in enumerate(targets):
        keyword = "if" if index == 0 else "elif"
        lines.append(
            f'        {keyword} state == "{_wait_state(target)}" and event == "{target}":'
        )
        if target in starts:
            constraint = starts[target]
            lines.append(f"            start_{constraint.name} = step")
        if target in ends:
            constraint = ends[target]
            lines.extend(
                [
                    f"            if start_{constraint.name} is None or step - start_{constraint.name} > {constraint.bound}:",
                    "                return False",
                ]
            )
        lines.append(f'            state = "{_destination(targets, index)}"')

    lines.append('    return state == "SUCCESS"')
    raw = "\n".join(lines) + "\n"
    return black.format_str(raw, mode=black.Mode(line_length=88))


def compile_monitor(source: str) -> Callable[[Sequence[str]], bool]:
    namespace: dict[str, object] = {}
    exec(compile(source, "<generated-explicit-timed-monitor>", "exec"), namespace)
    monitor = namespace["monitor"]
    if not callable(monitor):
        raise TypeError("Generated source did not define monitor")
    return monitor  # type: ignore[return-value]


def explicit_tree(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> TreeNode:
    states: list[TreeNode] = []
    for index, target in enumerate(targets):
        transition = TreeNode(f"Transition:{target}->{_destination(targets, index)}")
        states.append(TreeNode(f"State:{_wait_state(target)}", (transition,)))
    states.append(TreeNode("State:SUCCESS"))
    sequence = TreeNode("Sequence", tuple(states))

    timing_nodes = []
    for constraint in timing_constraints:
        timing_nodes.append(
            TreeNode(
                f"Constraint:{constraint.name}",
                (
                    TreeNode(f"Start:{constraint.start}"),
                    TreeNode(f"End:{constraint.end}"),
                    TreeNode(f"Bound:{constraint.bound}"),
                    TreeNode(f"StartVariable:start_{constraint.name}"),
                    TreeNode("TimingStartRule"),
                    TreeNode("DeadlineCheck"),
                ),
            )
        )
    timing = TreeNode("Timing", tuple(timing_nodes))
    return TreeNode("TimedMonitor", (sequence, timing))


def explicit_structural_metrics(
    targets: Sequence[str], timing_constraints: Sequence[TimingConstraint]
) -> dict[str, int]:
    m = len(timing_constraints)
    return {
        "explicit_states": len(targets) + 1,
        "explicit_transitions": len(targets),
        "explicit_branches": len(targets),
        "explicit_conditions": len(targets) + m,
        "explicit_variables": 1 + m,
        "explicit_timing_variables": m,
        "explicit_timing_start_rules": m,
        "explicit_deadline_checks": m,
        "explicit_numeric_bounds": m,
    }


def explicit_edit_metrics(
    before: Sequence[TimingConstraint], after: Sequence[TimingConstraint]
) -> dict[str, int]:
    before_by_name = {constraint.name: constraint for constraint in before}
    after_by_name = {constraint.name: constraint for constraint in after}
    added = set(after_by_name) - set(before_by_name)
    removed = set(before_by_name) - set(after_by_name)
    shared = set(before_by_name) & set(after_by_name)
    changed_checks = sum(before_by_name[name] != after_by_name[name] for name in shared)
    bounds_changed = sum(
        before_by_name[name].bound != after_by_name[name].bound for name in shared
    )
    return {
        "constraints_added": len(added),
        "constraints_removed": len(removed),
        "timing_variables_added": len(added),
        "timing_variables_removed": len(removed),
        "timing_start_rules_added": len(added),
        "timing_start_rules_removed": len(removed),
        "deadline_checks_added": len(added),
        "deadline_checks_removed": len(removed),
        "existing_checks_changed": changed_checks,
        "bounds_changed": bounds_changed,
    }
