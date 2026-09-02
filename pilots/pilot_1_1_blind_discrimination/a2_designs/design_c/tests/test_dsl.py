from __future__ import annotations

from pathlib import Path
import unittest

from warehouse_dsl import (
    AfterEach,
    AllOf,
    Between,
    DSLParseError,
    Visit,
    canonicalize,
    evaluate_task,
    parse_task,
)


def trace(*steps: str) -> tuple[frozenset[str], ...]:
    """Build a trace; each argument is a whitespace-separated label set."""

    return tuple(frozenset(step.split()) for step in steps)


class ParserAndCanonicalizerTests(unittest.TestCase):
    def test_public_parser_builds_immutable_closed_nodes(self) -> None:
        tree = parse_task("all(visit(A), after_each(A, between(1, 4, B)))")
        self.assertEqual(
            tree,
            AllOf(
                (
                    Visit("A"),
                    AfterEach("A", Between(1, 4, "B")),
                )
            ),
        )
        with self.assertRaises(AttributeError):
            tree.requirements = ()  # type: ignore[misc]

    def test_canonicalization_is_whitespace_insensitive_and_idempotent(self) -> None:
        source = "\n all ( visit(A) ,\n after_each( A, between( 1,4,B ) ) ) \n"
        canonical = "all(visit(A), after_each(A, between(1, 4, B)))"
        self.assertEqual(canonicalize(source), canonical)
        self.assertEqual(canonicalize(canonical), canonical)

    def test_unknown_construct_and_code_like_sources_are_rejected(self) -> None:
        invalid_sources = (
            "eventually(A)",
            "__import__(os)",
            "visit('A')",
            "visit(A); visit(B)",
            "all(visit(A))",
            "sequence(A)",
            "between(4, 2, B)",
            "between(-1, 2, B)",
            "visit(A, B)",
            "all(visit(A), visit(B),)",
            "",
        )
        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(DSLParseError):
                    parse_task(source)


class AtomicSemanticsTests(unittest.TestCase):
    def test_visit_and_avoid_include_the_whole_top_level_trace(self) -> None:
        self.assertTrue(evaluate_task("visit(A)", trace("", "A")))
        self.assertFalse(evaluate_task("visit(A)", ()))
        self.assertTrue(evaluate_task("avoid(X)", ()))
        self.assertFalse(evaluate_task("avoid(X)", trace("", "X")))

    def test_sequence_requires_strictly_increasing_positions(self) -> None:
        source = "sequence(A, B, C)"
        self.assertFalse(evaluate_task(source, trace("A B", "C")))
        self.assertTrue(evaluate_task(source, trace("B", "A", "", "B", "C")))
        self.assertFalse(evaluate_task(source, trace("A", "C", "B")))

    def test_between_uses_inclusive_offsets_and_ignores_early_visit(self) -> None:
        source = "after_each(A, between(2, 4, B))"
        self.assertTrue(evaluate_task(source, trace("A", "B", "B")))
        self.assertFalse(evaluate_task(source, trace("A", "B", "")))
        self.assertTrue(evaluate_task(source, trace("A", "", "", "", "B")))
        self.assertFalse(evaluate_task(source, trace("A", "", "", "", "", "B")))

    def test_avoid_until_excludes_goal_endpoint_from_avoidance(self) -> None:
        source = "avoid_until(X, C)"
        self.assertTrue(evaluate_task(source, trace("X C")))
        self.assertTrue(evaluate_task(source, trace("", "X C")))
        self.assertFalse(evaluate_task(source, trace("X", "C")))
        self.assertFalse(evaluate_task(source, trace("", "")))


class CompositionAndTriggerTests(unittest.TestCase):
    def test_after_each_is_vacuous_without_trigger_and_checks_every_trigger(self) -> None:
        source = "after_each(A, between(1, 4, B))"
        self.assertTrue(evaluate_task(source, trace("", "B")))
        self.assertTrue(evaluate_task(source, trace("A", "", "A", "B")))
        self.assertFalse(evaluate_task(source, trace("A", "B", "", "A")))

    def test_any_branch_is_selected_independently_per_trigger(self) -> None:
        source = "after_each(A, any(visit(B), visit(C)))"
        self.assertTrue(evaluate_task(source, trace("A", "C", "A", "B")))
        self.assertFalse(evaluate_task(source, trace("A", "B", "A", "")))

    def test_nested_requirement_starts_on_trigger_step(self) -> None:
        source = "after_each(B, avoid_until(X, C))"
        self.assertTrue(evaluate_task(source, trace("X", "B", "", "X C")))
        self.assertFalse(evaluate_task(source, trace("B X", "C")))
        self.assertTrue(evaluate_task(source, trace("B X C")))

    def test_immediate_response_rejects_final_trigger(self) -> None:
        source = "after_each(A, between(1, 1, B))"
        self.assertTrue(evaluate_task(source, trace("A", "B")))
        self.assertFalse(evaluate_task(source, trace("A")))

    def test_all_can_require_trigger_occurrence_separately(self) -> None:
        source = "all(visit(A), after_each(A, avoid_until(X, C)))"
        self.assertFalse(evaluate_task(source, trace("", "C")))
        self.assertTrue(evaluate_task(source, trace("A", "", "X C")))
        self.assertFalse(evaluate_task(source, trace("A", "X", "C")))


class TrainingArtifactTests(unittest.TestCase):
    ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "training_artifacts"

    def load(self, number: int) -> str:
        return (self.ARTIFACT_DIR / f"train_{number:02d}.wdsl").read_text(
            encoding="utf-8"
        )

    def test_all_fourteen_artifacts_exist_parse_and_are_canonical(self) -> None:
        files = sorted(self.ARTIFACT_DIR.glob("train_*.wdsl"))
        self.assertEqual([path.name for path in files], [f"train_{i:02d}.wdsl" for i in range(1, 15)])
        for path in files:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8").strip()
                parse_task(source)
                self.assertEqual(canonicalize(source), source)

    def test_each_training_artifact_has_positive_and_negative_witness(self) -> None:
        cases = {
            1: (trace("", "A"), trace("", "")),
            2: (trace("A", ""), trace("", "X")),
            3: (trace("A", "", "B"), trace("A B")),
            4: (trace("A", "", "", "", "B"), trace("A", "", "", "", "", "B")),
            5: (trace("", "X C"), trace("X", "C")),
            6: (trace("A", "", "C"), trace("A", "")),
            7: (trace("", "A"), trace("A", "X")),
            8: (trace("A", "B", "C"), trace("A", "C", "B")),
            9: (trace("A", "B"), trace("A", "", "B")),
            10: (trace("B", "", "X C"), trace("B", "X", "C")),
            11: (trace("", "D"), trace("A", "C")),
            12: (trace("A", "B", "B"), trace("A", "B", "")),
            13: (trace("A", "B", "C", "D"), trace("A", "B", "C", "", "", "D")),
            14: (trace("A", "", "X C"), trace("A", "X", "C")),
        }
        self.assertEqual(set(cases), set(range(1, 15)))
        for number, (positive, negative) in cases.items():
            source = self.load(number)
            with self.subTest(artifact=number, polarity="positive"):
                self.assertTrue(evaluate_task(source, positive))
            with self.subTest(artifact=number, polarity="negative"):
                self.assertFalse(evaluate_task(source, negative))

    def test_trace_container_contract_is_checked(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_task("visit(A)", [frozenset({"A"})])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            evaluate_task("visit(A)", ({"A"},))  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            evaluate_task("visit(A)", (frozenset({1}),))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
