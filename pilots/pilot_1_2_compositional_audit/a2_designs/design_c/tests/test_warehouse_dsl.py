"""Focused unittest suite for the warehouse DSL.

Run with:

    cd <this package's root directory>
    python3 -m unittest discover -s tests -v
"""

import dataclasses
import sys
import unittest
from pathlib import Path

# Make the package importable regardless of how the test runner sets up
# sys.path (the package lives one directory above this file).
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from warehouse_dsl import (  # noqa: E402
    WarehouseDSLError,
    WarehouseSyntaxError,
    WarehouseValidationError,
    canonicalize,
    evaluate_task,
    parse_task,
)

ARTIFACTS_DIR = _PACKAGE_ROOT / "training_artifacts"


def S(*labels: str) -> frozenset:
    """Shorthand for building one trace step."""
    return frozenset(labels)


def load_artifact(name: str) -> str:
    return (ARTIFACTS_DIR / name).read_text()


# ---------------------------------------------------------------------------
# Parsing: shape and immutability
# ---------------------------------------------------------------------------


class TestParsingBasics(unittest.TestCase):
    def test_visit_parses_to_expected_shape(self):
        tree = parse_task("visit(A)")
        self.assertEqual(tree, parse_task("visit(A)"))
        self.assertEqual(str(tree.target.name), "A")

    def test_whitespace_and_newlines_are_insignificant(self):
        compact = parse_task("every(A,within(B,1,4))")
        spaced = parse_task(
            "every( A ,\n  within(  B, 1,\t4  )\n)"
        )
        self.assertEqual(compact, spaced)

    def test_comments_are_ignored(self):
        with_comment = parse_task(
            "# a comment on its own line\n"
            "visit(A)  # trailing comment\n"
        )
        without_comment = parse_task("visit(A)")
        self.assertEqual(with_comment, without_comment)

    def test_any_target_parses_in_author_order(self):
        tree = parse_task("visit(any(B, C))")
        self.assertEqual(tree.target.labels, ("B", "C"))

    def test_tree_is_immutable(self):
        tree = parse_task("visit(A)")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            tree.target = None  # type: ignore[misc]

    def test_tree_is_hashable(self):
        tree = parse_task("every(A, within(B, 1, 4))")
        # Should not raise; frozen dataclasses of immutable fields hash.
        hash(tree)

    def test_within_then_nests_a_full_requirement(self):
        tree = parse_task("within(B, 1, 3, then=visit(C))")
        self.assertIsNotNone(tree.then)
        self.assertEqual(tree.then.target.name, "C")


# ---------------------------------------------------------------------------
# Parsing: malformed source is rejected with a ValueError subclass
# ---------------------------------------------------------------------------


class TestMalformedSourceRejected(unittest.TestCase):
    def assert_rejected(self, source: str):
        with self.assertRaises(WarehouseDSLError):
            parse_task(source)
        # Every raised error must be a ValueError, per the API contract.
        try:
            parse_task(source)
        except ValueError:
            pass
        else:
            self.fail("expected a ValueError subclass to be raised")

    def test_unknown_top_level_construct_is_rejected(self):
        self.assert_rejected("foobar(A)")

    def test_eval_is_not_a_construct(self):
        self.assert_rejected("eval(A)")

    def test_exec_is_not_a_construct(self):
        self.assert_rejected("exec('1+1')")

    def test_import_is_not_a_construct(self):
        self.assert_rejected("import(A)")

    def test_bare_label_is_not_a_task(self):
        self.assert_rejected("A")

    def test_empty_source_is_rejected(self):
        self.assert_rejected("")

    def test_trailing_garbage_after_valid_requirement_is_rejected(self):
        self.assert_rejected("visit(A) extra")

    def test_unclosed_paren_is_rejected(self):
        self.assert_rejected("visit(A")

    def test_missing_comma_is_rejected(self):
        self.assert_rejected("order(A B)")

    def test_negative_numbers_are_not_valid_tokens(self):
        self.assert_rejected("within(B, -1, 4)")

    def test_non_string_source_is_rejected(self):
        with self.assertRaises(WarehouseDSLError):
            parse_task(123)  # type: ignore[arg-type]

    def test_within_lo_greater_than_hi_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("within(B, 5, 1)")

    def test_order_with_one_target_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("order(A)")

    def test_and_with_one_child_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("and(visit(A))")

    def test_or_with_one_child_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("or(visit(A))")

    def test_any_with_one_label_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("visit(any(B))")

    def test_reserved_word_as_label_is_a_validation_error(self):
        with self.assertRaises(WarehouseValidationError):
            parse_task("visit(and)")

    def test_then_keyword_misspelled_is_rejected(self):
        self.assert_rejected("within(B, 1, 2, thenx=visit(C))")

    def test_unknown_construct_inside_every_is_rejected(self):
        self.assert_rejected("every(A, teleport(B))")


# ---------------------------------------------------------------------------
# canonicalize: determinism / idempotency / normalization
# ---------------------------------------------------------------------------


class TestCanonicalize(unittest.TestCase):
    def test_deterministic_across_calls(self):
        source = "every(A, within(B, 1, 4))"
        self.assertEqual(canonicalize(source), canonicalize(source))

    def test_idempotent(self):
        source = "or(and(order(A,B),avoid(X)),visit(D))"
        once = canonicalize(source)
        twice = canonicalize(once)
        self.assertEqual(once, twice)

    def test_strips_comments_and_normalizes_whitespace(self):
        messy = "  visit(  A  )   # a comment\n"
        self.assertEqual(canonicalize(messy), "visit(A)")

    def test_normalizes_leading_zeros(self):
        self.assertEqual(
            canonicalize("within(B, 01, 004)"), "within(B, 1, 4)"
        )

    def test_two_equivalent_spellings_canonicalize_identically(self):
        a = canonicalize("every(A,within(B,1,4))")
        b = canonicalize("every( A , within( B , 1 , 4 ) )  # note\n")
        self.assertEqual(a, b)

    def test_raises_on_malformed_source(self):
        with self.assertRaises(WarehouseDSLError):
            canonicalize("nonsense(A)")

    def test_all_training_artifacts_are_idempotent(self):
        for i in range(1, 17):
            name = f"train_{i:02d}.wdsl"
            with self.subTest(artifact=name):
                source = load_artifact(name)
                once = canonicalize(source)
                twice = canonicalize(once)
                self.assertEqual(once, twice)


# ---------------------------------------------------------------------------
# evaluate_task: one focused block of tests per construct
# ---------------------------------------------------------------------------


class TestVisit(unittest.TestCase):
    def test_true_when_label_present(self):
        self.assertTrue(evaluate_task("visit(A)", (S("A"),)))

    def test_false_when_label_absent(self):
        self.assertFalse(evaluate_task("visit(A)", (S("B"),)))

    def test_false_on_empty_trace(self):
        self.assertFalse(evaluate_task("visit(A)", ()))

    def test_any_of_matches_either_label(self):
        self.assertTrue(evaluate_task("visit(any(B, D))", (S("D"),)))
        self.assertTrue(evaluate_task("visit(any(B, D))", (S("B"),)))
        self.assertFalse(evaluate_task("visit(any(B, D))", (S("A"),)))


class TestAvoid(unittest.TestCase):
    def test_true_when_label_never_appears(self):
        self.assertTrue(evaluate_task("avoid(X)", (S("A"), S("B"))))

    def test_false_when_label_appears(self):
        self.assertFalse(evaluate_task("avoid(X)", (S("A"), S("X"))))

    def test_true_on_empty_trace(self):
        self.assertTrue(evaluate_task("avoid(X)", ()))


class TestOrder(unittest.TestCase):
    def test_true_for_strictly_increasing_visits(self):
        self.assertTrue(evaluate_task("order(A, B)", (S("A"), S("B"))))

    def test_earlier_occurrence_of_second_target_does_not_count(self):
        # B appears before A; there is no B strictly after A.
        self.assertFalse(evaluate_task("order(A, B)", (S("B"), S("A"))))

    def test_irrelevant_and_repeated_visits_allowed(self):
        trace = (S("X"), S("A"), S("A"), S("X"), S("B"), S("B"))
        self.assertTrue(evaluate_task("order(A, B)", trace))

    def test_three_way_order_requires_all_three_in_sequence(self):
        trace = (S("A"), S("B"), S("C"))
        self.assertTrue(evaluate_task("order(A, B, C)", trace))

    def test_three_way_order_fails_if_final_target_missing_after_prefix(self):
        # A then C then B: no C strictly after the chosen B.
        trace = (S("A"), S("C"), S("B"))
        self.assertFalse(evaluate_task("order(A, B, C)", trace))


class TestWithinNoFollowOn(unittest.TestCase):
    SOURCE = "every(A, within(B, 1, 4))"

    def test_true_when_b_lands_inside_window(self):
        trace = (S("A"), S(), S("B"), S(), S())
        self.assertTrue(evaluate_task(self.SOURCE, trace))

    def test_false_when_b_lands_outside_window(self):
        trace = (S("A"), S(), S(), S(), S(), S("B"))  # B at offset 5 > 4
        self.assertFalse(evaluate_task(self.SOURCE, trace))

    def test_trigger_step_itself_does_not_satisfy_the_deadline(self):
        # B at the same step as A (offset 0) is outside [1, 4].
        trace = (S("A", "B"),)
        self.assertFalse(evaluate_task(self.SOURCE, trace))

    def test_vacuously_true_if_trigger_never_occurs(self):
        self.assertTrue(evaluate_task(self.SOURCE, (S("B"),)))

    def test_lower_bound_excludes_steps_before_it(self):
        # train_14 shape: lo = 2, so offset 1 must not satisfy it.
        source = "every(C, within(D, 2, 4))"
        trace = (S("C"), S("D"))  # D at offset 1
        self.assertFalse(evaluate_task(source, trace))


class TestWithinThen(unittest.TestCase):
    def test_then_is_measured_from_the_chosen_step_visit(self):
        source = "every(A, within(B, 1, 3, then=visit(C)))"
        trace = (S("A"), S(), S("B"), S(), S("C"))
        self.assertTrue(evaluate_task(source, trace))

    def test_then_visit_fails_if_nothing_ever_reaches_c(self):
        source = "every(A, within(B, 1, 3, then=visit(C)))"
        trace = (S("A"), S("B"))
        self.assertFalse(evaluate_task(source, trace))

    def test_c_at_or_after_the_chosen_b_includes_the_b_step(self):
        source = "every(A, within(B, 1, 3, then=visit(C)))"
        trace = (S("A"), S(), S("B", "C"))  # B and C coincide
        self.assertTrue(evaluate_task(source, trace))

    def test_within_then_avoid_until_needs_existential_search(self):
        """The first B in the window fails its own follow-on (X sits on
        that very B step); only the second B in the window succeeds.
        This is only correct if the interpreter tries every matching
        step in the window rather than committing to the first match,
        matching warehouse.md: "If several B steps fall in the window,
        any one of them may serve, but the follow-on is measured from
        the one chosen."
        """
        source = "every(A, within(B, 1, 2, then=avoid_until(X, C)))"
        trace = (
            S("A"),        # index 0: trigger
            S("B", "X"),   # index 1: first candidate B, but X sits here too
            S("B"),        # index 2: second candidate B, clean
            S("C"),        # index 3: delivery
        )
        self.assertTrue(evaluate_task(source, trace))

    def test_if_every_candidate_in_window_fails_the_whole_thing_fails(self):
        source = "every(A, within(B, 1, 2, then=avoid_until(X, C)))"
        trace = (
            S("A"),
            S(),
            S("B"),   # only candidate, in window (offset 2)
            S("X"),   # X strictly between B (index 2) and C (index 4)
            S("C"),
        )
        self.assertFalse(evaluate_task(source, trace))


class TestAvoidUntil(unittest.TestCase):
    SOURCE = "avoid_until(X, C)"

    def test_true_when_no_x_before_c(self):
        self.assertTrue(evaluate_task(self.SOURCE, (S("A"), S("C"))))

    def test_false_when_x_strictly_before_c(self):
        self.assertFalse(evaluate_task(self.SOURCE, (S("X"), S("C"))))

    def test_x_allowed_on_the_c_step_itself(self):
        self.assertTrue(evaluate_task(self.SOURCE, (S(), S("C", "X"))))

    def test_false_when_c_never_occurs(self):
        self.assertFalse(evaluate_task(self.SOURCE, (S("A"), S("B"))))

    def test_false_on_empty_trace(self):
        self.assertFalse(evaluate_task(self.SOURCE, ()))

    def test_nested_forbidden_zone_includes_the_trigger_step(self):
        # every(B, avoid_until(X, C)): X coinciding with the triggering B
        # step must violate the "from that point" avoidance.
        source = "every(B, avoid_until(X, C))"
        trace = (S("B", "X"), S("C"))
        self.assertFalse(evaluate_task(source, trace))

    def test_nested_forbidden_zone_starts_at_trigger_not_trace_start(self):
        # X occurs before B (outside the "from that point" window), so it
        # must not count against the obligation that starts at B.
        source = "every(B, avoid_until(X, C))"
        trace = (S("X"), S("B"), S("C"))
        self.assertTrue(evaluate_task(source, trace))


class TestEvery(unittest.TestCase):
    def test_vacuously_true_when_trigger_never_occurs(self):
        self.assertTrue(evaluate_task("every(A, within(B, 1, 4))", (S("X"),)))

    def test_every_occurrence_must_independently_satisfy_body(self):
        source = "every(A, within(B, 1, 2))"
        # First A (index 0) is fine (B at 1). Second A (index 3) is not
        # (no B in [4, 5], trace ends at index 4).
        trace = (S("A"), S("B"), S(), S("A"), S())
        self.assertFalse(evaluate_task(source, trace))

    def test_every_visit_allows_same_step_as_trigger(self):
        # Design note in README: train_06's unqualified "afterwards" is
        # read as visit's usual at-or-after-start semantics.
        source = "every(A, visit(any(B, C)))"
        self.assertTrue(evaluate_task(source, (S("A", "B"),)))

    def test_different_triggers_may_satisfy_an_or_body_differently(self):
        # train_16 shape: one pickup uses the B-then-C option, another
        # uses the D option.
        source = "every(A, or(within(B, 1, 2, then=visit(C)), visit(D)))"
        trace = (
            S("A"),        # index 0: pickup 1
            S("B"),        # index 1: satisfies option 1's within
            S("C"),        # index 2: satisfies option 1's then
            S("A"),        # index 3: pickup 2
            S("D"),        # index 4: satisfies option 2 at-or-after index 3
        )
        self.assertTrue(evaluate_task(source, trace))


class TestAndOr(unittest.TestCase):
    def test_and_requires_all_children(self):
        source = "and(visit(A), avoid(X))"
        self.assertTrue(evaluate_task(source, (S("A"),)))
        self.assertFalse(evaluate_task(source, (S("B"),)))  # missing A
        self.assertFalse(evaluate_task(source, (S("A"), S("X"))))  # has X

    def test_or_requires_only_one_child(self):
        source = "or(visit(A), visit(D))"
        self.assertTrue(evaluate_task(source, (S("A"),)))
        self.assertTrue(evaluate_task(source, (S("D"),)))
        self.assertFalse(evaluate_task(source, (S("B"),)))

    def test_or_allows_both_disjuncts_to_hold(self):
        source = "or(visit(A), visit(D))"
        self.assertTrue(evaluate_task(source, (S("A", "D"),)))

    def test_avoid_inside_and_is_a_global_constraint_not_scoped_to_order(self):
        # train_13 design check: "never entering X" is whole-run, so an
        # X strictly after the ordered pair still breaks the plan even
        # though the order(A, B) portion already succeeded.
        source = "and(order(A, B), avoid(X))"
        trace = (S("A"), S("B"), S("X"))
        self.assertFalse(evaluate_task(source, trace))


# ---------------------------------------------------------------------------
# One evaluation round trip per training artifact: a satisfying trace and
# a violating trace for each, tying the sixteen sources back to the cards.
# ---------------------------------------------------------------------------


class TestTrainingArtifacts(unittest.TestCase):
    def test_all_artifacts_parse_and_are_immutable(self):
        for i in range(1, 17):
            name = f"train_{i:02d}.wdsl"
            with self.subTest(artifact=name):
                tree = parse_task(load_artifact(name))
                field_name = dataclasses.fields(tree)[0].name
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    setattr(tree, field_name, None)

    def test_train_01_visit_a(self):
        src = load_artifact("train_01.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"),)))
        self.assertFalse(evaluate_task(src, (S("B"),)))

    def test_train_02_avoid_x(self):
        src = load_artifact("train_02.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("B"))))
        self.assertFalse(evaluate_task(src, (S("A"), S("X"))))

    def test_train_03_order_a_b(self):
        src = load_artifact("train_03.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("B"))))
        self.assertFalse(evaluate_task(src, (S("B"), S("A"))))

    def test_train_04_every_a_within_b(self):
        src = load_artifact("train_04.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S(), S("B"), S(), S())))
        self.assertFalse(
            evaluate_task(src, (S("A"), S(), S(), S(), S(), S("B")))
        )
        self.assertTrue(evaluate_task(src, (S("X"),)))  # vacuous

    def test_train_05_avoid_x_until_c(self):
        src = load_artifact("train_05.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("C"))))
        self.assertFalse(evaluate_task(src, (S("X"), S("C"))))
        self.assertTrue(evaluate_task(src, (S(), S("C", "X"))))  # boundary

    def test_train_06_every_a_visit_b_or_c(self):
        src = load_artifact("train_06.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("C"))))
        self.assertFalse(evaluate_task(src, (S("A"), S("X"))))
        self.assertTrue(evaluate_task(src, (S("X"),)))  # vacuous

    def test_train_07_visit_a_and_avoid_x(self):
        src = load_artifact("train_07.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"),)))
        self.assertFalse(evaluate_task(src, (S("B"),)))
        self.assertFalse(evaluate_task(src, (S("A"), S("X"))))

    def test_train_08_order_a_b_c(self):
        src = load_artifact("train_08.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("B"), S("C"))))
        self.assertFalse(evaluate_task(src, (S("A"), S("C"), S("B"))))

    def test_train_09_every_b_avoid_until(self):
        src = load_artifact("train_09.wdsl")
        self.assertTrue(evaluate_task(src, (S("B"), S("C"))))
        self.assertFalse(evaluate_task(src, (S("B"), S("X"), S("C"))))
        self.assertTrue(evaluate_task(src, (S("A"),)))  # vacuous

    def test_train_10_visit_b_or_d(self):
        src = load_artifact("train_10.wdsl")
        self.assertTrue(evaluate_task(src, (S("D"),)))
        self.assertFalse(evaluate_task(src, (S("A"),)))

    def test_train_11_every_a_within_b_then_visit_c(self):
        src = load_artifact("train_11.wdsl")
        self.assertTrue(
            evaluate_task(src, (S("A"), S("B"), S(), S("C")))
        )
        self.assertFalse(evaluate_task(src, (S("A"), S("B"))))

    def test_train_12_every_a_within_b_then_avoid_until(self):
        src = load_artifact("train_12.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("B"), S("C"))))
        self.assertFalse(
            evaluate_task(
                src, (S("A"), S(), S("B"), S("X"), S("C"))
            )
        )

    def test_train_13_plan_one_or_plan_two(self):
        src = load_artifact("train_13.wdsl")
        self.assertTrue(evaluate_task(src, (S("A"), S("B"))))  # plan one
        self.assertTrue(evaluate_task(src, (S("D"),)))  # plan two
        self.assertFalse(evaluate_task(src, (S("A"),)))  # neither

    def test_train_14_every_c_within_d(self):
        src = load_artifact("train_14.wdsl")
        self.assertTrue(evaluate_task(src, (S("C"), S(), S(), S("D"))))
        self.assertFalse(evaluate_task(src, (S("C"), S("D"))))  # too soon

    def test_train_15_order_and_every_are_both_required(self):
        src = load_artifact("train_15.wdsl")
        self.assertTrue(evaluate_task(src, (S("C"), S("D"))))
        # order(C, D) holds (C at 0, D at 7) but the per-visit deadline
        # (D within [1, 5] of the C at 0) does not -- "in addition" means
        # both clauses are independently required.
        long_trace = (S("C"),) + (S(),) * 6 + (S("D"),)
        self.assertFalse(evaluate_task(src, long_trace))

    def test_train_16_every_a_option_b_then_c_or_option_d(self):
        src = load_artifact("train_16.wdsl")
        self.assertTrue(
            evaluate_task(src, (S("A"), S("B"), S("C")))
        )  # option 1
        self.assertTrue(evaluate_task(src, (S("A", "D"),)))  # option 2, same step
        self.assertFalse(evaluate_task(src, (S("A"),)))
        self.assertTrue(evaluate_task(src, (S("X"),)))  # vacuous


if __name__ == "__main__":
    unittest.main()
