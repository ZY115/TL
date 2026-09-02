from __future__ import annotations

import unittest
from dataclasses import dataclass

from neutral_ir import schema as neutral_schema

from .task_dsl import (
    AfterEach,
    Prefer,
    TaskSyntaxError,
    TaskValidationError,
    canonicalize,
    decode_task,
    encode_task,
    evaluate_expression,
    evaluate_task,
    format_task,
    parse_task,
    preference_rank,
    requirement_diagnostics,
)


@dataclass(frozen=True)
class Step:
    propositions: frozenset[str]
    resources: tuple[tuple[str, int], ...]

    def resource(self, name: str) -> int:
        return dict(self.resources)[name]


def step(*propositions: str, battery: int = 10, load: int = 0) -> Step:
    return Step(frozenset(propositions), (("battery", battery), ("load", load)))


TRACE = (
    step("S", "SAFE", battery=10),
    step("A", "SAFE", battery=9, load=1),
    step("B", "SAFE", battery=8, load=1),
    step("X", "HAZARD", battery=7, load=1),
    step("C", "SAFE", battery=6),
)


class RouteTaskTests(unittest.TestCase):
    def test_parse_format_is_canonical_and_round_trips(self) -> None:
        source = '''
          task "delivery" {
            require "r1" : route( "A","B", "C" ) ;
            require "r2": after_each("A", reach_between("B",1,10));
            require "quoted\\\"id": any_of(reach("D"), never("X"));
          }
        '''
        expected = (
            'task "delivery" {\n'
            '  require "r1": route("A", "B", "C");\n'
            '  require "r2": after_each("A", reach_between("B", 1, 10));\n'
            '  require "quoted\\\"id": any_of(reach("D"), never("X"));\n'
            '}\n'
        )
        task = parse_task(source)
        self.assertEqual(format_task(task), expected)
        self.assertEqual(canonicalize(expected), expected)
        self.assertEqual(parse_task(expected), task)

    def test_route_safety_deadline_count_and_resource_semantics(self) -> None:
        source = '''
        task "semantics" {
          require "route": route("A", "B", "C");
          require "deadline": reach_between("A", 1, 1);
          require "response": after_each("A", reach_between("B", 1, 1));
          require "count": visits_at_most("X", 1);
          require "battery": maintain_resource("battery", ">=", 6);
        }
        '''
        self.assertTrue(evaluate_task(source, TRACE))

        failing = '''
        task "failures" {
          require "hazard": never("X");
          require "battery": maintain_resource("battery", ">=", 7);
          require "until": avoid_until("X", "C");
        }
        '''
        diagnostics = requirement_diagnostics(parse_task(failing), TRACE)
        self.assertEqual(
            diagnostics, {"hazard": False, "battery": False, "until": False}
        )
        self.assertFalse(evaluate_task(failing, TRACE))

    def test_nested_history_alternatives_and_trigger_vacuity(self) -> None:
        source = '''
        task "nested" {
          require "past": after_each("B", seen("A"));
          require "choice": any_of(reach("D"), reach("C"));
          require "bundle": all_of(reach("A"), visits_at_most("X", 1));
          require "absent trigger": after_each("D", never("X"));
        }
        '''
        self.assertTrue(evaluate_task(source, TRACE))

        history = parse_task(
            'task "h" { require "r": after_each("C", '
            'condition_since("SAFE", "A")); }'
        ).requirements[0].expression
        self.assertIsInstance(history, AfterEach)
        self.assertFalse(evaluate_expression(history, TRACE))

    def test_strict_route_order_and_until_boundary(self) -> None:
        simultaneous = (
            step("A", "B"),
            step("X", "C"),
        )
        strict_route = 'task "t" { require "r": route("A", "B"); }'
        self.assertFalse(evaluate_task(strict_route, simultaneous))

        # Forbidden is permitted at the goal position because avoidance is
        # strict before the first goal.
        boundary = 'task "t" { require "r": avoid_until("X", "C"); }'
        self.assertTrue(evaluate_task(boundary, simultaneous))

    def test_preference_has_boolean_acceptance_and_separate_rank(self) -> None:
        task = parse_task(
            'task "p" { require "r": '
            'prefer(reach("D"), reach("C"), reach("A")); }'
        )
        expression = task.requirements[0].expression
        self.assertIsInstance(expression, Prefer)
        assert isinstance(expression, Prefer)
        self.assertTrue(evaluate_expression(expression, TRACE))
        self.assertEqual(preference_rank(expression, TRACE), 1)

    def test_mapping_trace_steps_are_supported(self) -> None:
        trace = [
            {"propositions": ["A"], "resources": {"battery": 5}},
            {"propositions": ["B"], "resources": {"battery": 4}},
        ]
        source = '''
        task "mapping" {
          require "route": route("A", "B");
          require "resource": maintain_resource("battery", ">", 3);
        }
        '''
        self.assertTrue(evaluate_task(source, trace))

    def test_neutral_authoring_bridge_is_lossless_and_canonical(self) -> None:
        neutral_task = neutral_schema.TaskSpec(
            "bridge",
            (
                neutral_schema.Requirement(
                    "nested",
                    neutral_schema.AllOf(
                        (
                            neutral_schema.On(
                                "A", neutral_schema.Deadline("B", 1, 10)
                            ),
                            neutral_schema.Priority(
                                (
                                    neutral_schema.Visit("C"),
                                    neutral_schema.Visit("D"),
                                )
                            ),
                        )
                    ),
                ),
                neutral_schema.Requirement(
                    "resource", neutral_schema.Threshold("battery", ">=", 5)
                ),
            ),
        )
        source = encode_task(neutral_task)
        self.assertEqual(
            source,
            (
                'task "bridge" {\n'
                '  require "nested": all_of(after_each("A", '
                'reach_between("B", 1, 10)), prefer(reach("C"), reach("D")));\n'
                '  require "resource": '
                'maintain_resource("battery", ">=", 5);\n'
                '}\n'
            ),
        )
        self.assertEqual(decode_task(source), neutral_task)
        self.assertEqual(canonicalize(source), source)

    def test_invalid_or_executable_looking_sources_are_rejected(self) -> None:
        cases: tuple[tuple[str, type[Exception]], ...] = (
            ('task "" { require "r": reach("A"); }', TaskValidationError),
            ('task "t" {}', TaskValidationError),
            (
                'task "t" { require "r": reach("A"); '
                'require "r": reach("B"); }',
                TaskValidationError,
            ),
            (
                'task "t" { require "r": reach_between("A", 4, 2); }',
                TaskValidationError,
            ),
            (
                'task "t" { require "r": visits_at_most("A", -1); }',
                TaskValidationError,
            ),
            ('task "t" { require "r": unknown("A"); }', TaskValidationError),
            (
                'task "t" { require "r": reach("A", "B"); }',
                TaskValidationError,
            ),
            (
                'task "t" { require "r": reach("A").system("x"); }',
                TaskSyntaxError,
            ),
            (
                'task "t" { require "r": __import__("os"); }',
                TaskValidationError,
            ),
        )
        for source, exception in cases:
            with self.subTest(source=source):
                with self.assertRaises(exception):
                    parse_task(source)


if __name__ == "__main__":
    unittest.main()
