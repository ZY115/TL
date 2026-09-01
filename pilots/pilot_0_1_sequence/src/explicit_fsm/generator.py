"""Generate and compile a canonical explicit Python FSM for each task."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import black

from src.tree_diff import TreeNode


def _wait_state(target: str) -> str:
    return f"WAIT_{target}"


def _transitions(targets: Sequence[str]) -> dict[str, tuple[str, str]]:
    transitions: dict[str, tuple[str, str]] = {}
    for index, target in enumerate(targets):
        destination = (
            _wait_state(targets[index + 1]) if index + 1 < len(targets) else "SUCCESS"
        )
        transitions[_wait_state(target)] = (target, destination)
    return transitions


def generate_source(targets: Sequence[str]) -> str:
    """Return Black-formatted task-specific explicit FSM source."""

    if not targets:
        raise ValueError("Pilot 0.1 tasks require at least one target")

    lines = [
        "def monitor(trajectory):",
        f'    state = "{_wait_state(targets[0])}"',
        "    for event in trajectory:",
    ]
    for index, (source, (event, destination)) in enumerate(
        _transitions(targets).items()
    ):
        keyword = "if" if index == 0 else "elif"
        lines.extend(
            [
                f'        {keyword} state == "{source}" and event == "{event}":',
                f'            state = "{destination}"',
            ]
        )
    lines.append('    return state == "SUCCESS"')
    raw = "\n".join(lines) + "\n"
    return black.format_str(raw, mode=black.Mode(line_length=88))


def compile_monitor(source: str) -> Callable[[Sequence[str]], bool]:
    """Compile a generated monitor so semantic tests exercise that source."""

    namespace: dict[str, object] = {}
    exec(compile(source, "<generated-explicit-fsm>", "exec"), namespace)
    monitor = namespace["monitor"]
    if not callable(monitor):
        raise TypeError("Generated source did not define a monitor function")
    return monitor  # type: ignore[return-value]


def fsm_tree(targets: Sequence[str]) -> TreeNode:
    """Return the task-level normalized FSM tree, excluding Python syntax."""

    states: list[TreeNode] = []
    for source, (event, destination) in _transitions(targets).items():
        transition = TreeNode(
            "Transition",
            (TreeNode(f"Event:{event}"), TreeNode(f"Destination:{destination}")),
        )
        states.append(TreeNode(f"State:{source}", (transition,)))
    states.append(TreeNode("State:SUCCESS"))
    return TreeNode("FSM", tuple(states))


def fsm_structural_metrics(targets: Sequence[str]) -> dict[str, int]:
    """Return explicitly documented FSM counts."""

    n = len(targets)
    return {
        "fsm_states": n + 1,
        "fsm_transitions": n,
        "fsm_conditions": n,
        "fsm_variables": 1,
        "fsm_branches": n,
    }


def fsm_modification_metrics(
    before: Sequence[str], after: Sequence[str]
) -> dict[str, int]:
    """Compare task-level states, transitions, guards, and dependencies."""

    before_transitions = _transitions(before)
    after_transitions = _transitions(after)
    before_states = set(before_transitions) | {"SUCCESS"}
    after_states = set(after_transitions) | {"SUCCESS"}

    shared_sources = set(before_transitions) & set(after_transitions)
    transitions_changed = sum(
        before_transitions[source] != after_transitions[source]
        for source in shared_sources
    )

    before_conditions = {
        (source, event) for source, (event, _destination) in before_transitions.items()
    }
    after_conditions = {
        (source, event) for source, (event, _destination) in after_transitions.items()
    }

    return {
        "states_added": len(after_states - before_states),
        "states_removed": len(before_states - after_states),
        "transitions_added": len(set(after_transitions) - set(before_transitions)),
        "transitions_removed": len(set(before_transitions) - set(after_transitions)),
        "transitions_changed": transitions_changed,
        "conditions_added": len(after_conditions - before_conditions),
        "conditions_removed": len(before_conditions - after_conditions),
        "existing_dependencies_changed": transitions_changed,
    }
