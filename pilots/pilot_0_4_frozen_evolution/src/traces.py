"""Deterministic, pairwise, and structured-random traces for Pilot 0.4."""

from __future__ import annotations

import random
from collections.abc import Sequence

from .base_traces import deterministic_groups as base_deterministic_groups
from .model import stages_for_k
from .oracle import REQUIREMENT_KEYS, evolution_oracle, evolution_oracle_diagnostics


def _positive_trace(
    step: int,
    rng: random.Random,
    *,
    force_branches: dict[int, str] | None = None,
    force_requirements: Sequence[int] = (),
) -> list[str]:
    """Construct a legal cumulative trace without rejection sampling."""

    force_branches = dict(force_branches or {})
    force = set(force_requirements)
    if 2 in force or (step >= 2 and rng.random() < 0.55):
        force_branches.setdefault(2, "L")
    if 5 in force or (step >= 5 and rng.random() < 0.55):
        force_branches.setdefault(4, "L")
    if 4 in force and step >= 4:
        force_branches.setdefault(3, "R")
    branches = {
        index: force_branches.get(index, rng.choice(("L", "R")))
        for index in range(1, 5)
    }
    trace = ["S"]

    if step >= 3 and (3 in force or rng.random() < 0.55):
        trace.append("H")
        trace.extend(["O"] * rng.randint(0, 2))
        trace.append("REC")
    if step >= 6 and (6 in force or rng.random() < 0.55):
        trace.append("J")
        if rng.random() < 0.5:
            trace.extend(["O"] * rng.randint(0, 1))
            trace.append("C")
        else:
            trace.extend(["O"] * rng.randint(0, 4))
            trace.append("D")

    if rng.random() < 0.4:
        # A legal decisions-first schedule varies selected-goal completion order.
        choices_goals = [
            (
                f"{branches[index]}{index}",
                f"{'P' if branches[index] == 'L' else 'Q'}{index}",
            )
            for index in range(1, 5)
        ]
        trace.extend(choice for choice, _goal in choices_goals)
        goals = [goal for _choice, goal in choices_goals]
        rng.shuffle(goals)
        trace.extend(goals)
        if step >= 2 and branches[2] == "L":
            trace.append("Z2")
        elif step >= 2 and rng.random() < 0.25:
            trace.append("Z2")
        if step >= 4 and branches[3] == "R" and rng.random() < 0.5:
            trace.append("Y3")  # after Q3 is outside the avoid-until interval
        if step >= 5 and branches[4] == "L":
            trace.extend(("N1", "N2"))
        elif step >= 5 and rng.random() < 0.25:
            trace.extend(("N1", "N2"))
    else:
        for index in range(1, 5):
            branch = branches[index]
            choice = f"{branch}{index}"
            goal = f"{'P' if branch == 'L' else 'Q'}{index}"
            if step >= 4 and index == 3 and branch == "R" and rng.random() < 0.25:
                trace.append("Y3")  # allowed before activation
            trace.append(choice)
            if rng.random() < 0.25:
                trace.append("O")
            trace.append(goal)
            if step >= 2 and index == 2 and branch == "L":
                trace.append("Z2")
            elif step >= 2 and index == 2 and branch == "R" and rng.random() < 0.25:
                trace.append("Z2")  # inactive and irrelevant
            if (
                step >= 4
                and index == 3
                and branch == "R"
                and "Y3" not in trace
                and rng.random() < 0.25
            ):
                trace.append("Y3")  # allowed after Q3
            if step >= 5 and index == 4 and branch == "L":
                trace.extend(("N1", "N2"))
            elif step >= 5 and index == 4 and branch == "R" and rng.random() < 0.25:
                trace.extend(("N1", "N2"))  # inactive and irrelevant
    trace.extend(["O"] * rng.randint(0, 2))
    trace.append("E")
    if not evolution_oracle(trace, step):
        raise AssertionError(f"Constructed positive was rejected at E{step}: {trace}")
    return trace


def positive_trace(
    step: int,
    *,
    seed: int = 0,
    force_requirements: Sequence[int] = (),
    force_branches: dict[int, str] | None = None,
) -> list[str]:
    return _positive_trace(
        step,
        random.Random(seed),
        force_requirements=force_requirements,
        force_branches=force_branches,
    )


def _targeted_negative(step: int, target: int, rng: random.Random) -> list[str]:
    force_branches: dict[int, str] = {1: "L"}
    if target == 2:
        force_branches[2] = "L"
    if target == 4:
        force_branches[3] = "R"
    if target == 5:
        force_branches[4] = "L"
    trace = _positive_trace(
        step,
        rng,
        force_branches=force_branches,
        force_requirements=tuple(range(1, step + 1)),
    )
    if target == 1:
        trace.insert(trace.index("E"), "BAD")
    elif target == 2:
        trace.remove("Z2")
    elif target == 3:
        h, rec = trace.index("H"), trace.index("REC")
        trace[h + 1 : rec] = ["O", "O", "O"]
    elif target == 4:
        if "Y3" in trace:
            trace.remove("Y3")
        trace.insert(trace.index("Q3"), "Y3")
    elif target == 5:
        n1, n2 = trace.index("N1"), trace.index("N2")
        trace[n1], trace[n2] = trace[n2], trace[n1]
    elif target == 6:
        for response in ("C", "D"):
            if response in trace:
                trace.remove(response)
        j = trace.index("J")
        # Replace any old J-response padding with a canonical distance-six D.
        while j + 1 < len(trace) and trace[j + 1] == "O":
            trace.pop(j + 1)
        trace[j + 1 : j + 1] = ["O"] * 5 + ["D"]
    else:
        raise ValueError("target requirement must be in 1..6")

    diagnostics = evolution_oracle_diagnostics(trace, step)
    intended_key = REQUIREMENT_KEYS[target - 1]
    active_failures = [key for key, value in diagnostics.items() if value is False]
    if active_failures != [intended_key]:
        raise AssertionError(
            f"Targeted E{target} mutation failed {active_failures}, expected {intended_key}: {trace}"
        )
    return trace


def targeted_negative(step: int, target: int, *, seed: int = 0) -> list[str]:
    return _targeted_negative(step, target, random.Random(seed))


def deterministic_base_groups() -> dict[str, list[list[str]]]:
    return base_deterministic_groups(stages_for_k(4))


def deterministic_requirement_cases(step: int) -> list[list[str]]:
    if step == 0:
        return []
    if step == 1:
        valid = _positive_trace(step, random.Random(31))
        early = list(valid)
        early.insert(1, "BAD")
        before_end = list(valid)
        before_end.insert(before_end.index("E"), "BAD")
        return [valid, early, before_end]
    elif step == 2:
        valid = _positive_trace(step, random.Random(32), force_branches={2: "L"})
        missing = list(valid)
        missing.remove("Z2")
        wrong_order = list(valid)
        wrong_order.remove("Z2")
        wrong_order.insert(wrong_order.index("P2"), "Z2")
        inactive = _positive_trace(step, random.Random(33), force_branches={2: "R"})
        if "Z2" in inactive:
            inactive.remove("Z2")
        inactive_with_z = list(inactive)
        inactive_with_z.insert(inactive_with_z.index("E"), "Z2")
        return [valid, missing, wrong_order, inactive, inactive_with_z]
    elif step == 3:
        valid = _positive_trace(step, random.Random(34), force_requirements=(3,))
        h, rec = valid.index("H"), valid.index("REC")
        distance_one = list(valid)
        distance_one[h + 1 : rec] = []
        distance_three = list(valid)
        distance_three[h + 1 : rec] = ["O", "O"]
        distance_four = list(valid)
        distance_four[h + 1 : rec] = ["O", "O", "O"]
        response_before = list(distance_one)
        response_before.remove("REC")
        response_before.insert(response_before.index("H"), "REC")
        early_end = list(distance_one)
        early_end.remove("REC")
        early_end.remove("H")
        early_end.insert(early_end.index("E"), "H")
        no_h = list(distance_one)
        no_h.remove("REC")
        no_h.remove("H")
        return [
            no_h,
            distance_one,
            distance_three,
            distance_four,
            response_before,
            early_end,
        ]
    elif step == 4:
        valid = _positive_trace(step, random.Random(35), force_branches={3: "R"})
        if "Y3" in valid:
            valid.remove("Y3")
        between = list(valid)
        between.insert(between.index("Q3"), "Y3")
        before = list(valid)
        before.insert(before.index("R3"), "Y3")
        after = list(valid)
        after.insert(after.index("Q3") + 1, "Y3")
        inactive = _positive_trace(step, random.Random(36), force_branches={3: "L"})
        if "Y3" not in inactive:
            inactive.insert(inactive.index("E"), "Y3")
        return [valid, between, before, after, inactive]
    elif step == 5:
        valid = _positive_trace(step, random.Random(37), force_branches={4: "L"})
        swapped = list(valid)
        n1, n2 = swapped.index("N1"), swapped.index("N2")
        swapped[n1], swapped[n2] = swapped[n2], swapped[n1]
        missing_n2 = list(valid)
        missing_n2.remove("N2")
        missing_n1 = list(valid)
        missing_n1.remove("N1")
        inactive = _positive_trace(step, random.Random(38), force_branches={4: "R"})
        for event in ("N1", "N2"):
            if event in inactive:
                inactive.remove(event)
        before_trigger = list(valid)
        before_trigger.remove("N1")
        before_trigger.remove("N2")
        insertion = before_trigger.index("L4")
        before_trigger[insertion:insertion] = ["N1", "N2"]
        return [valid, swapped, missing_n1, missing_n2, inactive, before_trigger]
    elif step == 6:
        base = _positive_trace(step, random.Random(39))
        for event in ("J", "C", "D"):
            if event in base:
                base.remove(event)

        def with_j(events: Sequence[str]) -> list[str]:
            trace = list(base)
            trace[1:1] = list(events)
            return trace

        return [
            base,
            with_j(("J", "C")),
            with_j(("J", "O", "C")),
            with_j(("J", "O", "O", "C", "O", "O", "D")),
            with_j(("J", "O", "O", "O", "O", "D")),
            with_j(("J", "O", "O", "O", "O", "O", "D")),
            with_j(("J", "O", "O", "C", "D")),
            with_j(("J", "C", "O", "O", "O", "O", "O", "D")),
            with_j(("J", "C", "D")),
            with_j(("J", "O", "O", "C", "O", "O", "D")),
            with_j(("C", "D", "J")),
        ]
    raise AssertionError("Unreachable evolution step")


def pairwise_interaction_traces(step: int) -> list[list[str]]:
    if step <= 1:
        return []
    traces: list[list[str]] = []
    for earlier in range(1, step):
        positive = _positive_trace(
            step,
            random.Random(40_000 + 100 * step + earlier),
            force_requirements=(earlier, step),
        )
        negative = _targeted_negative(
            step, step, random.Random(50_000 + 100 * step + earlier)
        )
        diagnostics = evolution_oracle_diagnostics(negative, step)
        if diagnostics[REQUIREMENT_KEYS[earlier - 1]] is not True:
            raise AssertionError(
                "Pairwise negative does not satisfy earlier requirement"
            )
        traces.extend((positive, negative))
    return traces


def structured_random_groups(
    step: int, *, seed: int, count: int = 10_000
) -> dict[str, list[list[str]]]:
    if count < 10_000:
        raise ValueError("Pilot 0.4 requires at least 10,000 random traces per step")
    rng = random.Random(seed)
    valid_count = 4_000
    base_invalid_count = 6_000 if step == 0 else 2_000
    requirement_count = 0 if step == 0 else 4_000
    valid = [_positive_trace(step, rng) for _ in range(valid_count)]
    base_invalid = []
    for _ in range(base_invalid_count):
        trace = _positive_trace(step, rng, force_branches={1: "L"})
        trace.remove("P1")
        if evolution_oracle_diagnostics(trace, step)["base_B4"] is not False:
            raise AssertionError("Base-invalid mutation did not fail B4")
        base_invalid.append(trace)
    requirement_violation = [
        _targeted_negative(step, sample % step + 1, rng)
        for sample in range(requirement_count)
    ]
    return {
        "structured_random_valid": valid,
        "structured_random_base_invalid": base_invalid,
        "structured_random_requirement_violation": requirement_violation,
    }
