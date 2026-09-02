from pathlib import Path
import unittest

from warehouse_dsl import DSLSyntaxError, canonicalize, evaluate_task, parse_task


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "training_artifacts"


def source(number: int) -> str:
    return (ARTIFACTS / f"train_{number:02d}.task").read_text(encoding="utf-8")


def trace(*steps: str) -> tuple[frozenset[str], ...]:
    """Use strings like 'A X' to make compact immutable test traces."""

    return tuple(frozenset(step.split()) for step in steps)


class TrainingArtifactTests(unittest.TestCase):
    def assert_accepts(self, number: int, *steps: str) -> None:
        self.assertTrue(evaluate_task(source(number), trace(*steps)))

    def assert_rejects(self, number: int, *steps: str) -> None:
        self.assertFalse(evaluate_task(source(number), trace(*steps)))

    def test_01_required_visit(self) -> None:
        self.assert_accepts(1, "", "A")
        self.assert_rejects(1, "", "B")
        self.assertFalse(evaluate_task(source(1), ()))

    def test_02_global_avoidance(self) -> None:
        self.assert_accepts(2, "A", "")
        self.assert_rejects(2, "", "X")

    def test_03_strict_order(self) -> None:
        self.assert_accepts(3, "B", "A", "", "B")
        self.assert_rejects(3, "A B")
        self.assert_rejects(3, "B", "A")

    def test_04_each_trigger_has_one_to_four_step_response(self) -> None:
        self.assert_accepts(4, "A", "", "B", "A", "", "", "", "B")
        self.assert_accepts(4, "B", "")  # trigger absence is vacuous
        self.assert_rejects(4, "A", "", "", "", "", "B")
        self.assert_rejects(4, "A")

    def test_05_until_and_endpoint_exception(self) -> None:
        self.assert_accepts(5, "A", "X C")
        self.assert_rejects(5, "X", "C")
        self.assert_rejects(5, "A", "B")

    def test_06_response_alternative(self) -> None:
        self.assert_accepts(6, "A", "C")
        self.assert_accepts(6, "")
        self.assert_rejects(6, "A", "D")

    def test_07_conjunction(self) -> None:
        self.assert_accepts(7, "", "A")
        self.assert_rejects(7, "A", "X")
        self.assert_rejects(7, "B")

    def test_08_three_strict_milestones(self) -> None:
        self.assert_accepts(8, "A", "A", "B", "C")
        self.assert_rejects(8, "A", "B C")

    def test_09_immediate_response_and_final_trigger(self) -> None:
        self.assert_accepts(9, "A", "B", "A", "B")
        self.assert_rejects(9, "A", "", "B")
        self.assert_rejects(9, "", "A")

    def test_10_triggered_until(self) -> None:
        self.assert_accepts(10, "B", "", "X C")
        self.assert_rejects(10, "B", "X", "C")
        self.assert_rejects(10, "B", "")
        self.assert_accepts(10, "A")

    def test_11_eventual_disjunction(self) -> None:
        self.assert_accepts(11, "A", "D")
        self.assert_rejects(11, "A", "C")

    def test_12_lower_bound_excludes_early_only_response(self) -> None:
        self.assert_rejects(12, "A", "B")
        self.assert_accepts(12, "A", "B", "B")
        self.assert_accepts(12, "A", "", "", "", "B")

    def test_13_independent_rules(self) -> None:
        self.assert_accepts(13, "A C", "B", "D")
        self.assert_rejects(13, "A C", "B", "", "D")
        self.assert_rejects(13, "A", "", "", "", "B")

    def test_14_required_trigger_and_until_rule(self) -> None:
        self.assert_accepts(14, "A", "", "X C")
        self.assert_rejects(14, "B", "C")
        self.assert_rejects(14, "A", "X", "C")
        self.assert_rejects(14, "A", "")


class LanguageTests(unittest.TestCase):
    def test_all_artifacts_parse_and_are_canonical(self) -> None:
        for number in range(1, 15):
            with self.subTest(number=number):
                text = source(number)
                parse_task(text)
                self.assertEqual(canonicalize(text), text)
                self.assertEqual(canonicalize(canonicalize(text)), text)

    def test_whitespace_is_canonicalized(self) -> None:
        messy = "all{seen A;after A{within 1..4{seen B}}}"
        expected = (
            "all {\n"
            "  seen A;\n"
            "  after A {\n"
            "    within 1..4 {\n"
            "      seen B\n"
            "    }\n"
            "  };\n"
            "}\n"
        )
        self.assertEqual(canonicalize(messy), expected)

    def test_unknown_and_malformed_constructs_are_rejected(self) -> None:
        invalid_sources = (
            "eventually A",
            "seen A trailing",
            "all {}",
            "order [A]",
            "never []",
            "never [X, X]",
            "within 4..2 { seen B }",
            "after A { seen B; seen C }",
            "seen 'A'",
            "seen A # comment",
        )
        for text in invalid_sources:
            with self.subTest(source=text):
                with self.assertRaises(DSLSyntaxError):
                    parse_task(text)

    def test_every_after_trigger_is_checked(self) -> None:
        task = "after A { within 1..2 { seen B } }"
        self.assertTrue(evaluate_task(task, trace("A", "B", "A", "", "B")))
        self.assertFalse(evaluate_task(task, trace("A", "B", "A", "", "")))

    def test_order_can_require_two_separate_occurrences_of_one_label(self) -> None:
        task = "order [A, A]"
        self.assertTrue(evaluate_task(task, trace("A", "", "A")))
        self.assertFalse(evaluate_task(task, trace("A")))

    def test_within_is_relative_to_current_window(self) -> None:
        task = "after A { within 2..2 { seen B } }"
        self.assertFalse(evaluate_task(task, trace("A B", "", "")))
        self.assertTrue(evaluate_task(task, trace("A B", "", "B")))

    def test_until_starts_at_nested_trigger(self) -> None:
        task = "after B { until C avoiding [X] }"
        self.assertTrue(evaluate_task(task, trace("X", "B", "C")))
        self.assertFalse(evaluate_task(task, trace("B X", "", "C")))
        self.assertTrue(evaluate_task(task, trace("B X C")))

    def test_trace_shape_is_checked(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_task("seen A", [frozenset({"A"})])  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            evaluate_task("seen A", ({"A"},))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
