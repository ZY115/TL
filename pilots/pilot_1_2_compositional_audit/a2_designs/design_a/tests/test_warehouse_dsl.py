"""Focused unittest suite for the warehouse DSL.

Covers: parser acceptance/rejection, canonicalize determinism and
idempotency, per-construct finite-trace semantics (including the boundary
cases warehouse.md calls out explicitly), and every training_artifacts
source evaluated against a hand-built satisfying and violating trace.

Run from the package root with:
    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from pathlib import Path

# Make the package importable regardless of how this file is invoked
# (e.g. `python3 -m unittest discover -s tests` from the package root, or
# running this file directly from within tests/).
_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

from warehouse_dsl import (  # noqa: E402
    AllOf,
    AnyOf,
    Avoid,
    AvoidUntil,
    Every,
    Order,
    Visit,
    Within,
    WarehouseSyntaxError,
    canonicalize,
    evaluate_task,
    parse_task,
)

TRAINING_DIR = Path(_PACKAGE_ROOT) / "training_artifacts"


def S(labels: str) -> frozenset:
    """Build a step's label set from a short string, e.g. S('AB') ->
    frozenset({'A', 'B'}). S('') is the empty step.
    """

    return frozenset(labels)


E = frozenset()  # a step with no labels


# ---------------------------------------------------------------------------
# Parser: acceptance
# ---------------------------------------------------------------------------


class TestParseValid(unittest.TestCase):
    def test_all_eight_constructs_parse(self):
        cases = {
            "visit(A)": Visit,
            "avoid(A)": Avoid,
            "avoid_until(X, C)": AvoidUntil,
            "order(A, B)": Order,
            "within(1, 4, B)": Within,
            "every(A, visit(B))": Every,
            "all_of(visit(A), avoid(X))": AllOf,
            "any_of(visit(A), avoid(X))": AnyOf,
        }
        for source, cls in cases.items():
            with self.subTest(source=source):
                tree = parse_task(source)
                self.assertIsInstance(tree, cls)

    def test_labelset_single_and_braced(self):
        self.assertEqual(parse_task("visit(A)").labels, frozenset({"A"}))
        self.assertEqual(
            parse_task("visit({A, B})").labels, frozenset({"A", "B"})
        )
        # order of labels inside braces must not matter semantically
        self.assertEqual(
            parse_task("visit({B, A})").labels, parse_task("visit({A, B})").labels
        )

    def test_within_then_chain_nests_arbitrarily(self):
        tree = parse_task(
            "within(1, 2, B) then within(1, 2, D) then visit(C)"
        )
        self.assertIsInstance(tree, Within)
        self.assertIsInstance(tree.followon, Within)
        self.assertIsInstance(tree.followon.followon, Visit)

    def test_comments_and_whitespace_ignored(self):
        source = """
        # a comment
        every(  A ,   # trigger
            within(1, 2, B) then visit(C)
        )  # trailing comment
        """
        tree = parse_task(source)
        self.assertIsInstance(tree, Every)

    def test_multi_char_labels_allowed(self):
        tree = parse_task("visit(SHELF_A)")
        self.assertEqual(tree.labels, frozenset({"SHELF_A"}))

    def test_tree_is_immutable_and_hashable(self):
        tree = parse_task("every(A, within(1, 2, B) then visit(C))")
        with self.assertRaises(Exception):
            tree.trigger = frozenset({"Z"})
        hash(tree)  # must not raise


# ---------------------------------------------------------------------------
# Parser: rejection
# ---------------------------------------------------------------------------


class TestParseErrors(unittest.TestCase):
    def assert_rejected(self, source: str):
        with self.assertRaises(WarehouseSyntaxError):
            parse_task(source)

    def test_is_value_error_subclass(self):
        self.assertTrue(issubclass(WarehouseSyntaxError, ValueError))

    def test_empty_source(self):
        self.assert_rejected("")
        self.assert_rejected("   \n  # only a comment\n")

    def test_unknown_construct_rejected(self):
        self.assert_rejected("xor(A, B)")
        self.assert_rejected("eventually(A)")
        self.assert_rejected("globally(A)")
        self.assert_rejected("F(A)")
        self.assert_rejected("G(A)")
        self.assert_rejected("U(A, B)")

    def test_no_escape_hatch(self):
        # These must be rejected as ordinary unknown/malformed constructs --
        # there is no code path in the parser that executes Python at all.
        self.assert_rejected("eval(A)")
        self.assert_rejected("exec(A)")
        self.assert_rejected('__import__("os")')
        self.assert_rejected("import os")
        self.assert_rejected("A and B")
        self.assert_rejected("lambda: True")
        self.assert_rejected("visit(A) or avoid(X)")

    def test_wrong_arity_rejected(self):
        self.assert_rejected("visit()")
        self.assert_rejected("visit(A, B)")
        self.assert_rejected("avoid_until(X)")
        self.assert_rejected("avoid_until(X, C, D)")
        self.assert_rejected("order(A)")
        self.assert_rejected("all_of(visit(A))")
        self.assert_rejected("any_of(visit(A))")
        self.assert_rejected("within(1, 2)")
        self.assert_rejected("every(A)")

    def test_malformed_bounds_rejected(self):
        self.assert_rejected("within(4, 1, B)")  # hi < lo
        self.assert_rejected("within(1, B, C)")  # non-numeric lo... actually
        self.assert_rejected("within(A, 2, B)")  # label where number expected

    def test_malformed_labelset_rejected(self):
        self.assert_rejected("visit(a)")  # lowercase is not a label
        self.assert_rejected("visit({})")  # empty braces
        self.assert_rejected("visit({A,A})")  # duplicate
        self.assert_rejected("visit({A, B)")  # unbalanced brace
        self.assert_rejected("visit(1A)")  # cannot start with a digit... (tokenizes as NUMBER then ident)

    def test_then_only_after_within(self):
        self.assert_rejected("visit(A) then visit(B)")
        self.assert_rejected("avoid(X) then visit(B)")
        self.assert_rejected("order(A, B) then visit(C)")
        self.assert_rejected("then visit(B)")

    def test_unbalanced_brackets_rejected(self):
        self.assert_rejected("visit(A")
        self.assert_rejected("every(A, visit(B)")
        self.assert_rejected("visit(A))")

    def test_trailing_input_rejected(self):
        self.assert_rejected("visit(A) visit(B)")
        self.assert_rejected("visit(A) garbage")

    def test_non_string_source_rejected(self):
        with self.assertRaises(WarehouseSyntaxError):
            parse_task(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# canonicalize: determinism / idempotency
# ---------------------------------------------------------------------------


class TestCanonicalize(unittest.TestCase):
    def test_idempotent_on_hand_written_sources(self):
        sources = [
            "visit(A)",
            "every(A, visit({B, C}))",
            "avoid(X)",
            "order(A, B, C)",
            "avoid_until(X, C)",
            "every(A, within(1, 4, B))",
            "all_of(visit(A), avoid(X))",
            "any_of(all_of(order(A, B), avoid(X)), visit(D))",
            "every(A, any_of(within(1, 2, B) then visit(C), visit(D)))",
        ]
        for source in sources:
            with self.subTest(source=source):
                once = canonicalize(source)
                twice = canonicalize(once)
                self.assertEqual(once, twice)

    def test_whitespace_and_comments_do_not_affect_canonical_form(self):
        compact = "every(A,within(1,4,B))"
        spread = """
        # header comment
        every(
            A,           # trigger label
            within(1, 4, B)   # bounded response
        )
        """
        self.assertEqual(canonicalize(compact), canonicalize(spread))

    def test_labelset_member_order_does_not_affect_canonical_form(self):
        self.assertEqual(canonicalize("visit({B, A})"), canonicalize("visit({A, B})"))

    def test_canonical_form_reflects_structure(self):
        self.assertNotEqual(
            canonicalize("within(1, 4, B)"), canonicalize("within(1, 5, B)")
        )
        self.assertNotEqual(canonicalize("visit(A)"), canonicalize("avoid(A)"))

    def test_canonicalize_rejects_malformed_source(self):
        with self.assertRaises(WarehouseSyntaxError):
            canonicalize("bogus(A)")

    def test_all_training_artifacts_canonicalize_idempotently(self):
        for path in sorted(TRAINING_DIR.glob("train_*.wdsl")):
            with self.subTest(path=path.name):
                source = path.read_text()
                once = canonicalize(source)
                twice = canonicalize(once)
                self.assertEqual(once, twice)


# ---------------------------------------------------------------------------
# Semantics: visit / avoid
# ---------------------------------------------------------------------------


class TestVisit(unittest.TestCase):
    def test_visit_true_and_false(self):
        self.assertTrue(evaluate_task("visit(A)", (E, S("A"), E)))
        self.assertFalse(evaluate_task("visit(A)", (E, E, E)))

    def test_visit_empty_trace_is_false(self):
        self.assertFalse(evaluate_task("visit(A)", ()))

    def test_visit_disjunctive_labels_either_suffices(self):
        self.assertTrue(evaluate_task("visit({B, D})", (E, S("D"), E)))
        self.assertTrue(evaluate_task("visit({B, D})", (S("B"), E)))
        self.assertFalse(evaluate_task("visit({B, D})", (S("A"), E)))

    def test_visit_as_every_body_includes_trigger_step(self):
        # "Evaluation begins at the trigger step": a label co-occurring
        # with the trigger already satisfies visit(...) -- the trigger
        # step is not exempt/excluded the way it is for within(...).
        self.assertTrue(evaluate_task("every(A, visit({B, C}))", (S("AB"),)))

    def test_visit_as_every_body_true_when_strictly_later(self):
        self.assertTrue(
            evaluate_task("every(A, visit({B, C}))", (S("A"), E, S("C")))
        )

    def test_visit_as_every_body_vacuous_when_trigger_absent(self):
        self.assertTrue(evaluate_task("every(A, visit({B, C}))", (E, E)))

    def test_after_construct_was_removed(self):
        # A previous revision had a separate "after(...)" construct with
        # exclusive-of-trigger semantics; it was removed as wrong (see
        # README, "Worked example: the trigger step counts") rather than
        # kept as a redundant, correctly-inclusive duplicate of visit.
        with self.assertRaises(WarehouseSyntaxError):
            parse_task("after(A)")


class TestAvoid(unittest.TestCase):
    def test_avoid_true_without_violation(self):
        self.assertTrue(evaluate_task("avoid(X)", (S("A"), E, S("B"))))

    def test_avoid_false_on_any_occurrence(self):
        self.assertFalse(evaluate_task("avoid(X)", (S("A"), S("X"), E)))

    def test_avoid_vacuously_true_on_empty_trace(self):
        self.assertTrue(evaluate_task("avoid(X)", ()))


# ---------------------------------------------------------------------------
# Semantics: avoid_until (top-level and nested)
# ---------------------------------------------------------------------------


class TestAvoidUntil(unittest.TestCase):
    def test_top_level_true_when_clean(self):
        self.assertTrue(evaluate_task("avoid_until(X, C)", (E, E, S("C"))))

    def test_top_level_false_when_x_before_c(self):
        self.assertFalse(evaluate_task("avoid_until(X, C)", (S("X"), E, S("C"))))

    def test_x_allowed_on_c_step(self):
        self.assertTrue(evaluate_task("avoid_until(X, C)", (E, S("XC"))))

    def test_false_when_c_never_occurs(self):
        self.assertFalse(evaluate_task("avoid_until(X, C)", (E, E, E)))

    def test_nested_forbidden_window_includes_trigger_step(self):
        # B and X co-occur exactly at the trigger step; C only comes later.
        # warehouse.md: "evaluation begins at the trigger step" -- the
        # trigger step is treated like a fresh step 0, and step 0 counts
        # as part of "strictly before C" whenever it precedes C.
        trace = (E, E, S("BX"), E, E, S("C"))
        self.assertFalse(evaluate_task("every(B, avoid_until(X, C))", trace))

    def test_nested_clean_is_true(self):
        trace = (E, E, S("B"), E, E, S("C"))
        self.assertTrue(evaluate_task("every(B, avoid_until(X, C))", trace))

    def test_nested_x_strictly_between_is_false(self):
        trace = (E, E, S("B"), E, S("X"), S("C"))
        self.assertFalse(evaluate_task("every(B, avoid_until(X, C))", trace))

    def test_nested_x_on_c_step_is_allowed(self):
        trace = (E, E, S("B"), E, E, S("CX"))
        self.assertTrue(evaluate_task("every(B, avoid_until(X, C))", trace))

    def test_nested_vacuous_when_trigger_absent(self):
        self.assertTrue(evaluate_task("every(B, avoid_until(X, C))", (E, E)))

    def test_earliest_c_witness_is_conclusive(self):
        # X occurs before the *first* C; a later, second C cannot rescue it,
        # since the forbidden window for any later C only gets larger.
        trace = (S("X"), S("C"), E, S("C"))
        self.assertFalse(evaluate_task("avoid_until(X, C)", trace))


# ---------------------------------------------------------------------------
# Semantics: order
# ---------------------------------------------------------------------------


class TestOrder(unittest.TestCase):
    def test_two_step_order_true(self):
        self.assertTrue(evaluate_task("order(A, B)", (S("A"), E, S("B"))))

    def test_two_step_order_false_when_reversed_only(self):
        self.assertFalse(evaluate_task("order(A, B)", (S("B"), S("A"))))

    def test_early_visit_does_not_block_later_completion(self):
        # An earlier B (before A) must not count as the required later one;
        # a later B after A must still complete the requirement.
        self.assertTrue(evaluate_task("order(A, B)", (S("B"), S("A"), S("B"))))

    def test_repeated_and_irrelevant_visits_allowed(self):
        self.assertTrue(
            evaluate_task("order(A, B)", (S("A"), S("A"), E, S("Q"), S("B")))
        )

    def test_three_step_order(self):
        self.assertTrue(evaluate_task("order(A, B, C)", (S("A"), S("B"), S("C"))))
        self.assertFalse(evaluate_task("order(A, B, C)", (S("A"), S("C"), S("B"))))

    def test_order_false_when_unfinished(self):
        self.assertFalse(evaluate_task("order(A, B)", (S("A"), E)))


# ---------------------------------------------------------------------------
# Semantics: within, with and without a follow-on
# ---------------------------------------------------------------------------


class TestWithin(unittest.TestCase):
    def test_bounds_are_inclusive_and_exclude_trigger(self):
        trace = (S("A"), E, E, S("B"), E)  # B at offset 3
        self.assertTrue(evaluate_task("every(A, within(1, 4, B))", trace))

    def test_out_of_window_is_false(self):
        trace = (S("A"), E, E, E, E, S("B"))  # B at offset 5, window is 1..4
        self.assertFalse(evaluate_task("every(A, within(1, 4, B))", trace))

    def test_trigger_step_itself_does_not_count(self):
        trace = (S("AB"),)  # B at offset 0 only; window starts at offset 1
        self.assertFalse(evaluate_task("every(A, within(1, 4, B))", trace))

    def test_window_partly_past_end_of_trace_still_checks_in_bounds_part(self):
        trace = (S("A"), E, S("B"))  # trace ends at index 2; window is 1..4
        self.assertTrue(evaluate_task("every(A, within(1, 4, B))", trace))

    def test_window_entirely_past_end_of_trace_is_false(self):
        trace = (S("A"),)  # window 1..4 has no in-bounds indices at all
        self.assertFalse(evaluate_task("every(A, within(1, 4, B))", trace))

    def test_followon_measured_from_chosen_witness(self):
        trace = (S("A"), E, S("B"), E, S("C"))
        self.assertTrue(
            evaluate_task("every(A, within(1, 3, B) then visit(C))", trace)
        )

    def test_followon_false_when_never_satisfied(self):
        trace = (S("A"), E, S("B"), E, E)
        self.assertFalse(
            evaluate_task("every(A, within(1, 3, B) then visit(C))", trace)
        )

    def test_existential_witness_first_fails_second_succeeds(self):
        # Two B's in the window: from the first (offset 1, co-occurring
        # with X) the avoid_until follow-on fails; from the second
        # (offset 2, clean) it succeeds. "Any one of them may serve."
        trace = (S("A"), S("BX"), S("B"), S("C"))
        self.assertTrue(
            evaluate_task(
                "every(A, within(1, 2, B) then avoid_until(X, C))", trace
            )
        )

    def test_top_level_within_without_trigger(self):
        # within is not restricted to appear only inside every.
        self.assertTrue(evaluate_task("within(1, 2, B)", (E, S("B"), E)))
        self.assertFalse(evaluate_task("within(1, 2, B)", (S("B"), E, E)))


# ---------------------------------------------------------------------------
# Semantics: every (vacuous truth, per-occurrence independence)
# ---------------------------------------------------------------------------


class TestEvery(unittest.TestCase):
    def test_vacuous_when_trigger_never_occurs(self):
        self.assertTrue(evaluate_task("every(A, within(1, 4, B))", (E, E, E)))

    def test_fails_if_any_single_occurrence_fails(self):
        # First A satisfied, second A not.
        trace = (S("A"), S("B"), E, S("A"), E, E, E)
        self.assertFalse(evaluate_task("every(A, within(1, 2, B))", trace))

    def test_different_occurrences_may_use_different_branches(self):
        # First pickup uses the within-then-visit branch; second pickup
        # (co-occurring with D) uses the direct visit(D) branch.
        trace = (S("A"), S("B"), E, S("C"), E, S("AD"))
        source = "every(A, any_of(within(1, 2, B) then visit(C), visit(D)))"
        self.assertTrue(evaluate_task(source, trace))


# ---------------------------------------------------------------------------
# Semantics: all_of / any_of
# ---------------------------------------------------------------------------


class TestAllOfAnyOf(unittest.TestCase):
    def test_all_of_requires_every_part(self):
        self.assertTrue(evaluate_task("all_of(visit(A), avoid(X))", (S("A"), E)))
        self.assertFalse(evaluate_task("all_of(visit(A), avoid(X))", (E, E)))
        self.assertFalse(
            evaluate_task("all_of(visit(A), avoid(X))", (S("A"), S("X")))
        )

    def test_any_of_is_inclusive_or(self):
        source = "any_of(all_of(order(A, B), avoid(X)), visit(D))"
        # Both plans complete: still True (inclusive, not exclusive-or).
        trace_both = (S("A"), S("B"), S("D"))
        self.assertTrue(evaluate_task(source, trace_both))
        # Only plan two: True.
        trace_plan2 = (E, E, S("D"))
        self.assertTrue(evaluate_task(source, trace_plan2))
        # Hazard breaks plan one, but plan two still rescues it.
        trace_rescued = (S("A"), S("X"), S("B"), S("D"))
        self.assertTrue(evaluate_task(source, trace_rescued))
        # Neither plan: False.
        trace_neither = (E, E, E)
        self.assertFalse(evaluate_task(source, trace_neither))


# ---------------------------------------------------------------------------
# Every training card, evaluated end-to-end from its own artifact file
# ---------------------------------------------------------------------------


class TestTrainingArtifacts(unittest.TestCase):
    def _load(self, name: str) -> str:
        path = TRAINING_DIR / name
        self.assertTrue(path.is_file(), f"missing training artifact {name}")
        return path.read_text()

    def test_all_sixteen_files_present_and_parse(self):
        for i in range(1, 17):
            name = f"train_{i:02d}.wdsl"
            with self.subTest(name=name):
                source = self._load(name)
                parse_task(source)  # must not raise

    def test_train_01_visit_a(self):
        source = self._load("train_01.wdsl")
        self.assertTrue(evaluate_task(source, (E, S("A"), E)))
        self.assertFalse(evaluate_task(source, (E, E, E)))

    def test_train_02_avoid_x(self):
        source = self._load("train_02.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E)))
        self.assertFalse(evaluate_task(source, (S("A"), S("X"))))

    def test_train_03_order_a_then_b(self):
        source = self._load("train_03.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E, S("B"))))
        self.assertFalse(evaluate_task(source, (S("B"), S("A"))))

    def test_train_04_bounded_response(self):
        source = self._load("train_04.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E, E, S("B"))))
        self.assertFalse(evaluate_task(source, (S("A"), E, E, E, E, S("B"))))
        self.assertTrue(evaluate_task(source, (E, E)))  # vacuous

    def test_train_05_avoid_until(self):
        source = self._load("train_05.wdsl")
        self.assertTrue(evaluate_task(source, (E, S("C"))))
        self.assertFalse(evaluate_task(source, (S("X"), S("C"))))
        self.assertTrue(evaluate_task(source, (E, S("XC"))))

    def test_train_06_reach_b_or_c_disjunctive(self):
        source = self._load("train_06.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E, S("C"))))
        # Evaluation begins at the trigger step, so a B/C co-occurring
        # with the triggering A already satisfies it (same-step counts).
        self.assertTrue(evaluate_task(source, (S("AB"),)))
        self.assertFalse(evaluate_task(source, (S("A"), E, E)))  # never reached
        self.assertTrue(evaluate_task(source, (E, E)))  # vacuous

    def test_train_06_coordinator_counterexample(self):
        # Regression test for the reported contract violation: the last
        # step carries both the trigger A and the target B, and "evaluation
        # begins at the trigger step" means that step is its own witness.
        source = self._load("train_06.wdsl")
        trace = (S("BD"), S("AX"), S("A"), S("X"), S("AB"))
        self.assertTrue(evaluate_task(source, trace))

    def test_train_07_visit_and_avoid(self):
        source = self._load("train_07.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E)))
        self.assertFalse(evaluate_task(source, (E, E)))
        self.assertFalse(evaluate_task(source, (S("A"), S("X"))))

    def test_train_08_three_step_order(self):
        source = self._load("train_08.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), S("B"), S("C"))))
        self.assertFalse(evaluate_task(source, (S("A"), S("C"), S("B"))))

    def test_train_09_every_b_avoid_until(self):
        source = self._load("train_09.wdsl")
        self.assertTrue(evaluate_task(source, (E, E, S("B"), E, E, S("C"))))
        self.assertFalse(evaluate_task(source, (E, E, S("BX"), E, E, S("C"))))

    def test_train_10_visit_b_or_d(self):
        source = self._load("train_10.wdsl")
        self.assertTrue(evaluate_task(source, (E, S("D"))))
        self.assertTrue(evaluate_task(source, (S("B"), E)))
        self.assertFalse(evaluate_task(source, (S("A"), E)))

    def test_train_11_within_then_eventually(self):
        source = self._load("train_11.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E, S("B"), E, S("C"))))
        self.assertFalse(evaluate_task(source, (S("A"), E, S("B"), E, E)))

    def test_train_12_within_then_avoid_until(self):
        source = self._load("train_12.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), S("B"), E, S("C"))))
        self.assertFalse(evaluate_task(source, (S("A"), S("B"), S("X"), S("C"))))

    def test_train_13_two_plans(self):
        source = self._load("train_13.wdsl")
        self.assertTrue(evaluate_task(source, (S("A"), E, S("B"))))  # plan 1
        self.assertTrue(evaluate_task(source, (E, E, S("D"))))  # plan 2
        self.assertFalse(evaluate_task(source, (E, E, E)))

    def test_train_14_every_c_within_2_4_d(self):
        source = self._load("train_14.wdsl")
        self.assertTrue(evaluate_task(source, (S("C"), E, E, S("D"), E)))
        self.assertFalse(evaluate_task(source, (S("C"), S("D"), E, E, E, E)))

    def test_train_15_order_and_every(self):
        source = self._load("train_15.wdsl")
        self.assertTrue(evaluate_task(source, (S("C"), E, S("D"))))
        # order holds (first C precedes the D) but the *second* C's own
        # 1-5 deadline is missed -- every(...) must fail even though
        # order(...) alone would pass.
        trace = (
            S("C"), E, S("D"), E, E, E,
            S("C"), E, E, E, E, E,
        )
        self.assertFalse(evaluate_task(source, trace))

    def test_train_16_per_pickup_choice(self):
        source = self._load("train_16.wdsl")
        # branch 1 for the only pickup
        self.assertTrue(
            evaluate_task(source, (S("A"), S("B"), E, S("C")))
        )
        # different pickups, different branches
        trace = (S("A"), S("B"), E, S("C"), E, S("AD"))
        self.assertTrue(evaluate_task(source, trace))
        # neither branch satisfied
        self.assertFalse(evaluate_task(source, (S("A"), E, E, E, E, E)))


# ---------------------------------------------------------------------------
# API-contract sanity checks
# ---------------------------------------------------------------------------


class TestApiContract(unittest.TestCase):
    def test_evaluate_task_returns_plain_bool(self):
        result = evaluate_task("visit(A)", (S("A"),))
        self.assertIsInstance(result, bool)

    def test_evaluate_task_raises_on_malformed_source(self):
        with self.assertRaises(WarehouseSyntaxError):
            evaluate_task("not_a_real_construct(A)", (S("A"),))

    def test_unfinished_trace_is_false_not_an_exception(self):
        # An until-goal that can never be resolved within a short trace
        # must evaluate to False, not raise.
        try:
            result = evaluate_task("avoid_until(X, C)", (S("X"),))
        except Exception as exc:  # pragma: no cover - defensive
            self.fail(f"evaluate_task raised {exc!r} instead of returning False")
        self.assertFalse(result)

    def test_canonicalize_output_is_reparseable_to_same_tree(self):
        source = "every(A, within(1, 2, B) then avoid_until(X, C))"
        canonical = canonicalize(source)
        self.assertEqual(parse_task(source), parse_task(canonical))


if __name__ == "__main__":
    unittest.main()
