"""Focused unittest suite for the Warehouse DSL.

Covers: parsing of every construct, rejection of malformed/unknown source,
canonicalize determinism/idempotence, and evaluate_task semantics -- both
directly against warehouse.md's rules and against all sixteen training
scenarios (one positive and at least one negative trace each).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from warehouse_dsl import (
    WarehouseDSLError,
    WarehouseDSLSyntaxError,
    WarehouseDSLValidationError,
    canonicalize,
    evaluate_task,
    parse_task,
)


def s(*labels):
    """Build one trace step (a frozenset of labels)."""
    return frozenset(labels)


EMPTY = s()


class ParseValidTests(unittest.TestCase):
    def test_visit_single(self):
        parse_task("(visit A)")

    def test_visit_multi(self):
        parse_task("(visit B D)")

    def test_never(self):
        parse_task("(never X)")

    def test_order_two(self):
        parse_task("(order A B)")

    def test_order_three(self):
        parse_task("(order A B C)")

    def test_avoid_until(self):
        parse_task("(avoid_until X C)")

    def test_whenever_within(self):
        parse_task("(whenever A (within 1 4 B))")

    def test_whenever_visit(self):
        parse_task("(whenever A (visit B C))")

    def test_whenever_avoid_until(self):
        parse_task("(whenever B (avoid_until X C))")

    def test_within_then_visit(self):
        parse_task("(whenever A (within 1 3 B (then (visit C))))")

    def test_within_then_avoid_until(self):
        parse_task("(whenever A (within 1 2 B (then (avoid_until X C))))")

    def test_all_of(self):
        parse_task("(all_of (visit A) (never X))")

    def test_either_top_level(self):
        parse_task("(either (all_of (order A B) (never X)) (visit D))")

    def test_either_scoped(self):
        parse_task("(whenever A (either (within 1 2 B (then (visit C))) (visit D)))")

    def test_all_of_three(self):
        parse_task("(all_of (visit A) (visit B) (never X))")

    def test_comments_and_whitespace_ignored(self):
        src = "# a comment\n(visit   A)  # trailing comment\n"
        node = parse_task(src)
        self.assertEqual(canonicalize(src), "(visit A)")
        self.assertIsNotNone(node)

    def test_within_lo_zero_allowed(self):
        parse_task("(whenever A (within 0 2 B))")


class ParseInvalidTests(unittest.TestCase):
    def test_empty_source(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("")

    def test_whitespace_only_source(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("   \n  # only a comment\n")

    def test_unknown_head(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(bogus A)")

    def test_visit_zero_labels(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(visit)")

    def test_order_one_label(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(order A)")

    def test_all_of_one_child(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(all_of (visit A))")

    def test_either_one_child(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(either (visit A))")

    def test_avoid_until_missing_second_label(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("(avoid_until X)")

    def test_within_bad_bounds(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(whenever A (within 4 1 B))")

    def test_within_not_allowed_top_level(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(within 1 4 B)")

    def test_then_not_allowed_top_level(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(then (visit A))")

    def test_order_not_allowed_inside_whenever(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(whenever A (order A B))")

    def test_never_not_allowed_inside_whenever(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(whenever A (never X))")

    def test_whenever_not_allowed_inside_whenever(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(whenever A (whenever B (visit C)))")

    def test_all_of_not_allowed_inside_whenever(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(whenever A (all_of (visit B) (visit C)))")

    def test_unbalanced_missing_close(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("(visit A")

    def test_trailing_tokens(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("(visit A) (visit B)")

    def test_no_leading_paren(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("A")

    def test_reserved_word_as_label(self):
        with self.assertRaises(WarehouseDSLValidationError):
            parse_task("(visit then)")

    def test_stray_character_rejected(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task("(visit A -> B)")

    def test_raw_ltl_rejected(self):
        with self.assertRaises(WarehouseDSLError):
            parse_task("G(A -> F(B))")

    def test_non_string_source(self):
        with self.assertRaises(WarehouseDSLSyntaxError):
            parse_task(12345)  # type: ignore[arg-type]

    def test_all_errors_are_value_errors(self):
        for bad in ["", "(bogus A)", "(visit)", "(order A)"]:
            try:
                parse_task(bad)
            except ValueError:
                pass
            else:
                self.fail(f"expected ValueError for {bad!r}")


class CanonicalizeTests(unittest.TestCase):
    SOURCES = [
        "(visit A)",
        "(visit B D)",
        "(never X)",
        "(order A B C)",
        "(avoid_until X C)",
        "(whenever A (within 1 4 B))",
        "(whenever A (visit B C))",
        "(all_of (visit A) (never X))",
        "(either (all_of (order A B) (never X)) (visit D))",
        "(whenever A (within 1 3 B (then (visit C))))",
        "(whenever A (within 1 2 B (then (avoid_until X C))))",
        "(whenever A (either (within 1 2 B (then (visit C))) (visit D)))",
        "(all_of (order C D) (whenever C (within 1 5 D)))",
    ]

    def test_idempotent(self):
        for src in self.SOURCES:
            once = canonicalize(src)
            twice = canonicalize(once)
            self.assertEqual(once, twice, msg=f"not idempotent for {src!r}")

    def test_deterministic_across_whitespace(self):
        messy = "  (   whenever   A\n(within 1   4 B)  )  # note\n"
        tidy = "(whenever A (within 1 4 B))"
        self.assertEqual(canonicalize(messy), canonicalize(tidy))

    def test_canonical_output_reparses_to_equal_tree(self):
        for src in self.SOURCES:
            tree1 = parse_task(src)
            tree2 = parse_task(canonicalize(src))
            self.assertEqual(tree1, tree2, msg=f"round trip changed tree for {src!r}")

    def test_rejects_malformed(self):
        with self.assertRaises(WarehouseDSLError):
            canonicalize("(bogus A)")


class EvaluateSemanticsTests(unittest.TestCase):
    """Direct checks of the finite-trace rules stated in warehouse.md,
    independent of any particular training card."""

    def test_visit_true_and_false(self):
        self.assertTrue(evaluate_task("(visit A)", (EMPTY, s("A"))))
        self.assertFalse(evaluate_task("(visit A)", (EMPTY, s("B"))))
        self.assertFalse(evaluate_task("(visit A)", ()))

    def test_never_whole_trace(self):
        self.assertTrue(evaluate_task("(never X)", (s("A"), s("B"))))
        self.assertFalse(evaluate_task("(never X)", (s("X"),)))
        self.assertTrue(evaluate_task("(never X)", ()))

    def test_order_strict_increase_and_same_step_fails(self):
        self.assertTrue(evaluate_task("(order A B)", (s("A"), s("B"))))
        self.assertFalse(evaluate_task("(order A B)", (s("B"), s("A"))))
        self.assertFalse(evaluate_task("(order A B)", (s("A", "B"),)))

    def test_order_early_occurrence_does_not_block_later_one(self):
        # "An early B does not prevent a later B from completing the
        # ordered requirement."
        self.assertTrue(evaluate_task("(order A B)", (s("B"), s("A"), s("B"))))

    def test_within_bounds_inclusive_trigger_excluded(self):
        # offset 0 (the trigger step) never counts
        self.assertFalse(evaluate_task("(whenever A (within 1 4 B))", (s("A", "B"),)))
        # offset 1..4 all count
        for offset in (1, 2, 3, 4):
            trace = [EMPTY] * (offset + 1)
            trace[0] = s("A")
            trace[offset] = s("B")
            self.assertTrue(
                evaluate_task("(whenever A (within 1 4 B))", tuple(trace)),
                msg=f"offset {offset} should satisfy within 1 4",
            )
        # offset 5 is out of range
        trace = [s("A"), EMPTY, EMPTY, EMPTY, EMPTY, s("B")]
        self.assertFalse(evaluate_task("(whenever A (within 1 4 B))", tuple(trace)))

    def test_whenever_vacuous_when_trigger_absent(self):
        self.assertTrue(evaluate_task("(whenever A (within 1 4 B))", (s("B"),)))
        self.assertTrue(evaluate_task("(whenever A (within 1 4 B))", ()))

    def test_whenever_applies_to_every_occurrence(self):
        src = "(whenever A (within 1 2 B))"
        # first A satisfied (B at +1), second A NOT satisfied
        trace = (s("A"), s("B"), s("A"), EMPTY, EMPTY)
        self.assertFalse(evaluate_task(src, trace))

    def test_avoid_until_basic(self):
        self.assertTrue(evaluate_task("(avoid_until X C)", (EMPTY, s("C"))))
        self.assertFalse(evaluate_task("(avoid_until X C)", (s("X"), s("C"))))
        self.assertFalse(evaluate_task("(avoid_until X C)", (s("X"), EMPTY)))

    def test_avoid_until_x_allowed_on_c_step(self):
        self.assertTrue(evaluate_task("(avoid_until X C)", (EMPTY, s("C", "X"))))

    def test_avoid_until_requires_a_c(self):
        self.assertFalse(evaluate_task("(avoid_until X C)", (EMPTY, EMPTY)))
        self.assertFalse(evaluate_task("(avoid_until X C)", ()))

    def test_avoid_until_nested_scope_starts_at_trigger(self):
        src = "(whenever B (avoid_until X C))"
        # X occurs before B, so it must not count against this window
        trace = (s("X"), s("B"), EMPTY, s("C"))
        self.assertTrue(evaluate_task(src, trace))
        # X occurs between B and C: forbidden
        trace2 = (s("B"), s("X"), s("C"))
        self.assertFalse(evaluate_task(src, trace2))
        # B and C coincide: forbidden window is empty, so X elsewhere is fine
        trace3 = (s("B", "C"),)
        self.assertTrue(evaluate_task(src, trace3))

    def test_either_inclusive_or(self):
        src = "(either (visit A) (visit D))"
        self.assertTrue(evaluate_task(src, (s("A"),)))
        self.assertTrue(evaluate_task(src, (s("D"),)))
        self.assertTrue(evaluate_task(src, (s("A", "D"),)))  # both is fine
        self.assertFalse(evaluate_task(src, (EMPTY,)))

    def test_all_of_conjunction(self):
        src = "(all_of (visit A) (never X))"
        self.assertTrue(evaluate_task(src, (s("A"),)))
        self.assertFalse(evaluate_task(src, (s("A", "X"),)))
        self.assertFalse(evaluate_task(src, (EMPTY,)))

    def test_within_then_at_or_after_chosen_b(self):
        # C must be at or after the *chosen* B, not merely anywhere.
        src = "(whenever A (within 1 3 B (then (visit C))))"
        # C occurs only before the single available B: must fail
        trace = (s("A"), s("C"), s("B"))
        self.assertFalse(evaluate_task(src, trace))
        # C at exactly the chosen B step counts ("at or after")
        trace2 = (s("A"), EMPTY, s("B", "C"))
        self.assertTrue(evaluate_task(src, trace2))

    def test_within_then_backtracks_over_candidate_choice(self):
        # Whether an early candidate B or a later candidate B is used can
        # change the outcome of an avoid_until follow-on, because a later
        # start shrinks the forbidden window. The interpreter must try
        # every candidate in the window, not just the first.
        src = "(whenever A (within 1 3 B (then (avoid_until X C))))"
        # B at offset 1 fails (X falls inside [B@1, C@4)); B at offset 3
        # succeeds (X@2 is before it, outside [B@3, C@4)).
        trace = (s("A"), s("B"), s("X"), s("B"), s("C"))
        self.assertTrue(evaluate_task(src, trace))


class TrainingCardScenarioTests(unittest.TestCase):
    """One positive and at least one negative trace per training card,
    evaluated against the exact source shipped in training_artifacts/."""

    ARTIFACT_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "training_artifacts",
    )

    def _load(self, name):
        path = os.path.join(self.ARTIFACT_DIR, f"{name}.wdsl")
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def test_train_01(self):
        src = self._load("train_01")
        self.assertTrue(evaluate_task(src, (s("A"),)))
        self.assertFalse(evaluate_task(src, (s("B"),)))

    def test_train_02(self):
        src = self._load("train_02")
        self.assertTrue(evaluate_task(src, (s("A"), s("B"))))
        self.assertFalse(evaluate_task(src, (s("A"), s("X"))))

    def test_train_03(self):
        src = self._load("train_03")
        self.assertTrue(evaluate_task(src, (s("A"), EMPTY, s("B"))))
        self.assertFalse(evaluate_task(src, (s("B"), s("A"))))

    def test_train_04(self):
        src = self._load("train_04")
        self.assertTrue(evaluate_task(src, (s("A"), EMPTY, EMPTY, s("B"))))
        self.assertFalse(evaluate_task(src, (s("A"), EMPTY, EMPTY, EMPTY, EMPTY, s("B"))))
        self.assertTrue(evaluate_task(src, (s("C"),)))  # A never occurs

    def test_train_05(self):
        src = self._load("train_05")
        self.assertTrue(evaluate_task(src, (EMPTY, s("C", "X"))))
        self.assertFalse(evaluate_task(src, (s("X"), s("C"))))

    def test_train_06(self):
        src = self._load("train_06")
        self.assertTrue(evaluate_task(src, (s("A"), s("C"))))
        self.assertFalse(evaluate_task(src, (s("A"), EMPTY)))

    def test_train_07(self):
        src = self._load("train_07")
        self.assertTrue(evaluate_task(src, (s("A"), EMPTY)))
        self.assertFalse(evaluate_task(src, (s("A"), s("X"))))
        self.assertFalse(evaluate_task(src, (EMPTY,)))

    def test_train_08(self):
        src = self._load("train_08")
        self.assertTrue(evaluate_task(src, (s("A"), s("B"), s("C"))))
        self.assertFalse(evaluate_task(src, (s("A"), s("C"), s("B"))))

    def test_train_09(self):
        src = self._load("train_09")
        self.assertTrue(evaluate_task(src, (s("B"), s("C"))))
        self.assertFalse(evaluate_task(src, (s("B"), s("X"), s("C"))))

    def test_train_10(self):
        src = self._load("train_10")
        self.assertTrue(evaluate_task(src, (s("D"),)))
        self.assertFalse(evaluate_task(src, (s("A"),)))

    def test_train_11(self):
        src = self._load("train_11")
        self.assertTrue(evaluate_task(src, (s("A"), s("B"), EMPTY, s("C"))))
        self.assertFalse(evaluate_task(src, (s("A"), s("B"), EMPTY, EMPTY)))

    def test_train_12(self):
        src = self._load("train_12")
        self.assertTrue(evaluate_task(src, (s("A"), s("B"), s("C"))))
        self.assertFalse(evaluate_task(src, (s("A"), s("B"), s("X"), s("C"))))

    def test_train_13(self):
        src = self._load("train_13")
        self.assertTrue(evaluate_task(src, (s("A"), s("B"))))  # plan one
        self.assertTrue(evaluate_task(src, (s("D"),)))  # plan two
        self.assertFalse(evaluate_task(src, (s("A"), s("X"))))  # neither plan

    def test_train_14(self):
        src = self._load("train_14")
        self.assertTrue(evaluate_task(src, (s("C"), EMPTY, s("D"))))
        self.assertFalse(evaluate_task(src, (s("C"), s("D"))))  # offset 1, too early

    def test_train_15(self):
        src = self._load("train_15")
        self.assertTrue(evaluate_task(src, (s("C"), s("D"))))
        trace = tuple([s("C")] + [EMPTY] * 9 + [s("D")])  # D far outside 1-5 window
        self.assertFalse(evaluate_task(src, trace))

    def test_train_16(self):
        src = self._load("train_16")
        self.assertTrue(evaluate_task(src, (s("A"), s("D"))))  # option two, D at trigger+1
        self.assertTrue(evaluate_task(src, (s("A"), s("B"), EMPTY, s("C"))))  # option one
        self.assertFalse(evaluate_task(src, (s("A"), EMPTY, EMPTY)))  # neither option

    def test_all_sixteen_parse_and_canonicalize_idempotently(self):
        for i in range(1, 17):
            name = f"train_{i:02d}"
            src = self._load(name)
            tree = parse_task(src)
            self.assertIsNotNone(tree)
            once = canonicalize(src)
            twice = canonicalize(once)
            self.assertEqual(once, twice, msg=f"{name} canonicalize not idempotent")


if __name__ == "__main__":
    unittest.main()
