from pathlib import Path
import unittest

from warehouse_dsl import DSLParseError, canonicalize, evaluate_task, parse_task


ROOT = Path(__file__).resolve().parents[1]


def trace(*steps: str) -> tuple[frozenset[str], ...]:
    return tuple(frozenset(step.split()) if step else frozenset() for step in steps)


def artifact(number: int) -> str:
    return (ROOT / "training_artifacts" / f"train_{number:02d}.wdsl").read_text()


class ArtifactSemanticsTests(unittest.TestCase):
    def assert_cases(self, number, positives, negatives):
        source = artifact(number)
        parse_task(source)
        for candidate in positives:
            with self.subTest(task=number, expected=True, trace=candidate):
                self.assertTrue(evaluate_task(source, candidate))
        for candidate in negatives:
            with self.subTest(task=number, expected=False, trace=candidate):
                self.assertFalse(evaluate_task(source, candidate))

    def test_train_01_eventually(self):
        self.assert_cases(1, [trace("A"), trace("", "A")], [trace(), trace("B")])

    def test_train_02_never(self):
        self.assert_cases(2, [trace(), trace("A", "")], [trace("X"), trace("A", "X")])

    def test_train_03_strict_sequence(self):
        self.assert_cases(
            3,
            [trace("A", "B"), trace("B", "A", "", "B")],
            [trace("A B"), trace("B", "A"), trace("A")],
        )

    def test_train_04_repeated_bounded_responses(self):
        self.assert_cases(
            4,
            [trace(), trace("A", "", "B"), trace("A", "A", "B")],
            [trace("A"), trace("A", "", "", "", "", "B")],
        )

    def test_train_05_avoid_until_endpoint(self):
        self.assert_cases(
            5,
            [trace("C X"), trace("", "C"), trace("A", "X C")],
            [trace(), trace("X", "C"), trace("A")],
        )

    def test_train_06_triggered_choice(self):
        self.assert_cases(
            6,
            [trace(), trace("A B"), trace("A", "", "C")],
            [trace("A"), trace("A", "B", "A")],
        )

    def test_train_07_conjunction(self):
        self.assert_cases(7, [trace("A"), trace("", "A")], [trace(), trace("A X")])

    def test_train_08_three_strict_milestones(self):
        self.assert_cases(
            8,
            [trace("A", "B", "C"), trace("C", "A", "B", "C")],
            [trace("A B", "C"), trace("A", "B C")],
        )

    def test_train_09_next_step(self):
        self.assert_cases(
            9,
            [trace(), trace("A", "B"), trace("A", "A B", "B")],
            [trace("A"), trace("A B"), trace("A", "", "B")],
        )

    def test_train_10_triggered_until(self):
        self.assert_cases(
            10,
            [trace(), trace("B C X"), trace("B", "", "C X")],
            [trace("B"), trace("B", "X", "C"), trace("B", "C", "B")],
        )

    def test_train_11_eventual_choice(self):
        self.assert_cases(11, [trace("B"), trace("", "D")], [trace(), trace("A", "C")])

    def test_train_12_lower_bound(self):
        self.assert_cases(
            12,
            [trace(), trace("A", "B", "B"), trace("A", "", "", "", "B")],
            [trace("A", "B"), trace("A", "", "", "", "", "B")],
        )

    def test_train_13_two_independent_rules(self):
        self.assert_cases(
            13,
            [trace(), trace("A C", "D", "B")],
            [trace("A C", "B"), trace("A C", "D", "", "", "B")],
        )

    def test_train_14_visit_and_each_until(self):
        self.assert_cases(
            14,
            [trace("A C X"), trace("A", "C", "A", "", "C X")],
            [trace(), trace("C"), trace("A", "X", "C"), trace("A", "C", "A")],
        )


class ParserAndApiTests(unittest.TestCase):
    def test_all_artifacts_round_trip_through_canonical_form(self):
        files = sorted((ROOT / "training_artifacts").glob("train_*.wdsl"))
        self.assertEqual(14, len(files))
        for path in files:
            with self.subTest(path=path.name):
                canonical = canonicalize(path.read_text())
                self.assertEqual(canonical, canonicalize(canonical))
                self.assertEqual(parse_task(canonical), parse_task(path.read_text()))

    def test_unknown_or_malformed_source_is_rejected(self):
        invalid = [
            "",
            "eventually A",
            "(sometimes A)",
            "(eventually A B)",
            "(sequence A)",
            "(within 4 2 B)",
            "(within -1 2 B)",
            "(all (eventually A))",
            "(eventually A) (never X)",
            "(after-each A (eventually B)",
            "(eventually invalid/label)",
        ]
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(DSLParseError):
                    parse_task(source)

    def test_nested_composition_uses_child_origin(self):
        source = "(after-each A (all (within 1 2 B) (avoid-until X C)))"
        self.assertTrue(evaluate_task(source, trace("A", "B", "C X")))
        self.assertFalse(evaluate_task(source, trace("A", "B X", "C")))

    def test_trace_contract_types_are_checked(self):
        with self.assertRaises(TypeError):
            evaluate_task("(eventually A)", [frozenset({"A"})])
        with self.assertRaises(TypeError):
            evaluate_task("(eventually A)", ({"A"},))
        with self.assertRaises(TypeError):
            evaluate_task("(eventually A)", (frozenset({1}),))


if __name__ == "__main__":
    unittest.main()
