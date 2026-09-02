from __future__ import annotations

import unittest
from dataclasses import dataclass

from neutral_ir import schema as neutral
from neutral_ir.interpreter import evaluate_ir
from solution import (
    Priority,
    TaskSourceError,
    Visit,
    canonicalize_task,
    encode_task,
    evaluate_task,
    format_task,
    parse_task,
    priority_rank,
)


@dataclass(frozen=True)
class Step:
    propositions: frozenset[str]
    resources: dict[str, int]

    def resource(self, name: str) -> int:
        return self.resources[name]


def step(*propositions: str, battery: int = 10, load: int = 0) -> Step:
    return Step(frozenset(propositions), {"battery": battery, "load": load})


def source(expression: str) -> str:
    return f'task "t" {{ require "r" = {expression}; }}'


class SpecializedDSLTests(unittest.TestCase):
    def test_all_training_constructs_parse_and_format_canonically(self) -> None:
        raw = r'''
            # Every expression form seen in training, with nesting.
            task "coverage" {
              require "r1" = visit("A");
              require "r2" = avoid("X");
              require "r3" = ordered_visit("A", "B", "C");
              require "r4" = deadline("A", 1, 10);
              require "r5" = maintain_until("X", "C");
              require "r6" = on("A", visit("B"));
              require "r7" = alternative(visit("A"), visit("D"));
              require "r8" = all_of(visit("A"), avoid("X"));
              require "r9" = count_at_most("X", 1);
              require "r10" = on("B", once("A"));
              require "r11" = on("C", since("SAFE", "A"));
              require "r12" = threshold("battery", >=, 5);
              require "r13" = priority(visit("C"), visit("D"));
              require "r14" = on("A", deadline("B", 1, 10));
            }
        '''
        parsed = parse_task(raw)
        canonical = format_task(parsed)
        self.assertEqual(parse_task(canonical), parsed)
        self.assertEqual(canonicalize_task(canonical), canonical)
        self.assertTrue(
            canonical.startswith(
                'task "coverage" {\n  require "r1" = visit("A");'
            )
        )

    def test_json_strings_have_deterministic_escaping(self) -> None:
        raw = 'task "a\\nb" { require "quote\\\"" = visit("点 A"); }'
        self.assertEqual(
            canonicalize_task(raw),
            'task "a\\nb" {\n  require "quote\\\"" = visit("点 A");\n}\n',
        )

    def test_neutral_ir_authoring_bridge_covers_closed_vocabulary(self) -> None:
        expressions = (
            neutral.Visit("A"),
            neutral.Avoid("X"),
            neutral.OrderedVisit(("A", "B", "C")),
            neutral.Deadline("A", 1, 10),
            neutral.MaintainUntil("X", "C"),
            neutral.On("A", neutral.Visit("B")),
            neutral.Alternative((neutral.Visit("A"), neutral.Visit("D"))),
            neutral.AllOf((neutral.Visit("A"), neutral.Avoid("X"))),
            neutral.CountAtMost("X", 1),
            neutral.Once("A"),
            neutral.Since("SAFE", "A"),
            neutral.Threshold("battery", ">=", 5),
            neutral.Priority((neutral.Visit("C"), neutral.Visit("D"))),
        )
        task = neutral.TaskSpec(
            "neutral-task",
            tuple(
                neutral.Requirement(f"req-{index}", expression)
                for index, expression in enumerate(expressions)
            ),
        )

        encoded = encode_task(task)
        parsed = parse_task(encoded)
        self.assertEqual(parsed.id, "neutral-task")
        self.assertEqual(
            tuple(item.id for item in parsed.requirements),
            tuple(f"req-{index}" for index in range(len(expressions))),
        )
        self.assertEqual(canonicalize_task(encoded), encoded)
        self.assertIn('threshold("battery", >=, 5)', encoded)

    def test_ordered_visit_requires_strictly_later_steps(self) -> None:
        ordered = source('ordered_visit("A", "B", "C")')
        self.assertTrue(
            evaluate_task(ordered, [step("A"), step("B"), step("C")])
        )
        self.assertFalse(evaluate_task(ordered, [step("A", "B"), step("C")]))

    def test_encoded_tasks_match_neutral_interpreter(self) -> None:
        expressions = (
            neutral.Visit("A"),
            neutral.Avoid("X"),
            neutral.OrderedVisit(("A", "B", "C")),
            neutral.Deadline("B", 1, 2),
            neutral.MaintainUntil("X", "C"),
            neutral.On("A", neutral.Deadline("B", 1, 2)),
            neutral.Alternative((neutral.Visit("A"), neutral.Visit("D"))),
            neutral.AllOf((neutral.Visit("A"), neutral.Avoid("X"))),
            neutral.CountAtMost("A", 1),
            neutral.On("B", neutral.Once("A")),
            neutral.On("C", neutral.Since("SAFE", "A")),
            neutral.Threshold("battery", ">=", 5),
            neutral.Priority((neutral.Visit("C"), neutral.Visit("D"))),
        )
        traces = (
            [step("A", "SAFE"), step("B", "SAFE"), step("C", "SAFE")],
            [step("X", battery=4), step("D", battery=3)],
            [step(), step("A"), step(), step("B")],
            [step()],
        )
        for index, expression in enumerate(expressions):
            task = neutral.TaskSpec(
                f"task-{index}",
                (neutral.Requirement("r", expression),),
            )
            encoded = encode_task(task)
            for trace in traces:
                with self.subTest(expression=type(expression).__name__, trace=trace):
                    self.assertEqual(
                        evaluate_task(encoded, trace),
                        evaluate_ir(task, trace),
                    )

    def test_deadline_is_inclusive_and_relative_to_each_trigger(self) -> None:
        task = source('on("A", deadline("B", 1, 2))')
        self.assertTrue(
            evaluate_task(task, [step(), step("A"), step(), step("B")])
        )
        self.assertFalse(
            evaluate_task(task, [step("A"), step("B"), step("A"), step()])
        )
        self.assertTrue(evaluate_task(task, [step("B")]))

    def test_maintain_until_checks_only_prefix_before_first_goal(self) -> None:
        task = source('maintain_until("X", "C")')
        self.assertTrue(evaluate_task(task, [step(), step("C", "X")]))
        self.assertFalse(evaluate_task(task, [step("X"), step("C")]))
        self.assertFalse(evaluate_task(task, [step(), step()]))

    def test_combinators_counts_and_multiple_requirements(self) -> None:
        task = '''
          task "compound" {
            require "choice" = alternative(visit("A"), visit("D"));
            require "constraints" = all_of(avoid("X"), count_at_most("A", 2));
          }
        '''
        self.assertTrue(evaluate_task(task, [step("A"), step(), step("A")]))
        self.assertFalse(evaluate_task(task, [step("A"), step("X")]))
        self.assertFalse(
            evaluate_task(task, [step("A"), step("A"), step("A")])
        )

    def test_once_and_since_use_history_at_trigger_position(self) -> None:
        once_task = source('on("B", once("A"))')
        self.assertTrue(
            evaluate_task(once_task, [step("A"), step(), step("B")])
        )
        self.assertFalse(evaluate_task(once_task, [step("B"), step("A")]))

        since_task = source('on("C", since("SAFE", "A"))')
        self.assertTrue(
            evaluate_task(
                since_task,
                [step("A", "SAFE"), step("SAFE"), step("C", "SAFE")],
            )
        )
        self.assertFalse(
            evaluate_task(
                since_task,
                [step("A", "SAFE"), step(), step("C", "SAFE")],
            )
        )

    def test_threshold_checks_every_step_and_priority_exposes_rank(self) -> None:
        threshold = source('threshold("battery", >=, 5)')
        self.assertTrue(
            evaluate_task(threshold, [step(battery=8), step(battery=5)])
        )
        self.assertFalse(
            evaluate_task(threshold, [step(battery=8), step(battery=4)])
        )

        expression = Priority((Visit("C"), Visit("D")))
        self.assertEqual(priority_rank(expression, [step("D"), step("C")]), 0)
        self.assertEqual(priority_rank(expression, [step("D")]), 1)
        self.assertIsNone(priority_rank(expression, [step()]))

    def test_invalid_or_executable_looking_source_is_rejected(self) -> None:
        bad_sources = (
            'task "t" { require "r" = __import__("os"); }',
            'task "t" { require "r" = visit("A", "B"); }',
            'task "t" { require "r" = deadline("A", 4, 2); }',
            'task "t" { require "r" = count_at_most("A", -1); }',
            'task "t" { require "r" = alternative(); }',
            'task "t" { require "r" = visit("A"); require "r" = avoid("X"); }',
            'task "t" { require "r" = visit(callback); }',
            'task "t" { require "r" = visit("A").anything; }',
            'task "t" {}',
        )
        for bad_source in bad_sources:
            with self.subTest(source=bad_source):
                with self.assertRaises(TaskSourceError):
                    parse_task(bad_source)


if __name__ == "__main__":
    unittest.main()
