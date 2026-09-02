from __future__ import annotations

import ast
from pathlib import Path

from src.compatibility import load_snapshot
from src.diff_metrics import directory_edit
from src.oracle import REQUIREMENT_KEYS, evolution_oracle, evolution_oracle_diagnostics
from src.traces import positive_trace, targeted_negative

ROOT = Path(__file__).resolve().parents[1]


def test_each_targeted_negative_violates_only_its_requirement() -> None:
    for step in range(1, 7):
        for target in range(1, step + 1):
            trace = targeted_negative(step, target, seed=100 * step + target)
            diagnostics = evolution_oracle_diagnostics(trace, step)
            failures = [key for key, value in diagnostics.items() if value is False]
            assert failures == [REQUIREMENT_KEYS[target - 1]]
            assert not evolution_oracle(trace, step)


def test_positive_constructor_covers_all_steps() -> None:
    for step in range(7):
        assert evolution_oracle(positive_trace(step, seed=step), step)


def test_until_exists_only_from_e4() -> None:
    for step in range(7):
        source = (ROOT / "systems" / "tl" / f"E{step}" / "syntax.py").read_text()
        assert ("class Until" in source) == (step >= 4)


def test_e5_infrastructure_reuses_e4_byte_identically() -> None:
    for system in ("tl", "specialized_dsl"):
        edit = directory_edit(
            ROOT / "systems" / system / "E4", ROOT / "systems" / system / "E5"
        )
        assert (
            sum(
                edit[key]
                for key in ("tokens_inserted", "tokens_deleted", "tokens_changed")
            )
            == 0
        )


def test_all_snapshots_are_importable_and_executable() -> None:
    for system in ("tl", "specialized_dsl"):
        for step in range(7):
            module = load_snapshot(ROOT / "systems" / system / f"E{step}", system, step)
            filename = "tl.task" if system == "tl" else "dsl.py"
            source = (ROOT / "tasks" / f"E{step}" / filename).read_text()
            assert module.evaluate_task(source, positive_trace(step, seed=1000 + step))


def test_capability_matrix_is_preregistered_exactly() -> None:
    expected = [
        ["Global invariant", "supported", "unsupported", "DSL"],
        ["Conditional post-sequence", "supported", "unsupported", "DSL"],
        ["Bounded response", "supported", "unsupported", "DSL"],
        ["Strong Until", "unsupported", "unsupported", "TL + DSL"],
        ["Second branch sequence", "supported", "supported after E2", "neither"],
        ["Disjunctive bounded response", "supported", "unsupported", "DSL"],
    ]
    rows = [
        line.split(",")
        for line in (ROOT / "capability_matrix.csv").read_text().splitlines()
    ]
    assert rows[1:] == expected
