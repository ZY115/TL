from __future__ import annotations

import unittest
from dataclasses import dataclass

from neutral_ir.schema import (
    AllOf as IRAllOf,
    Alternative as IRAlternative,
    Avoid as IRAvoid,
    CountAtMost as IRCountAtMost,
    Deadline as IRDeadline,
    MaintainUntil as IRMaintainUntil,
    On as IROn,
    Once as IROnce,
    OrderedVisit as IROrderedVisit,
    Priority as IRPriority,
    Requirement as IRRequirement,
    Since as IRSince,
    TaskSpec,
    Threshold as IRThreshold,
    Visit as IRVisit,
)

from .authoring import encode_task
from .interpreter import evaluate_expression, evaluate_task, priority_rank
from .model import Priority
from .parser import WTLParseError, format_task, parse_task


@dataclass(frozen=True)
class Step:
    propositions: frozenset[str]
    resources: tuple[tuple[str, int], ...] = (("battery", 40), ("load", 0))

    def resource(self, name: str) -> int:
        values = dict(self.resources)
        if name not in values:
            raise KeyError(name)
        return values[name]


def step(*propositions: str, battery: int = 40) -> Step:
    return Step(
        frozenset(propositions),
        (("battery", battery), ("load", 0)),
    )


class ParserTests(unittest.TestCase):
    def test_parse_format_is_canonical_and_round_trips(self) -> None:
        source = '''
          task "nested" {
            require "r1":on("A",deadline("B",1,10));
            require "r2": all_of( avoid("X") , threshold("battery",>=,5));
          }
        '''
        expected = (
            'task "nested" {\n'
            '  require "r1": on("A", deadline("B", 1, 10));\n'
            '  require "r2": all_of(avoid("X"), threshold("battery", >=, 5));\n'
            '}\n'
        )
        canonical = format_task(parse_task(source))
        self.assertEqual(canonical, expected)
        self.assertEqual(format_task(parse_task(canonical)), canonical)

    def test_unknown_construct_and_trailing_input_are_rejected(self) -> None:
        with self.assertRaises(WTLParseError):
            parse_task('task "x" { require "r": python("A"); }')
        with self.assertRaises(WTLParseError):
            parse_task('task "x" { require "r": visit("A"); } junk')

    def test_invalid_values_and_duplicate_ids_are_rejected(self) -> None:
        with self.assertRaises(WTLParseError):
            parse_task('task "x" { require "r": deadline("A", 4, 2); }')
        with self.assertRaises(WTLParseError):
            parse_task(
                'task "x" { require "r": visit("A"); '
                'require "r": avoid("X"); }'
            )

    def test_neutral_ir_authoring_is_complete_and_round_trips(self) -> None:
        task = TaskSpec(
            "all-fields",
            (
                IRRequirement("visit", IRVisit("A")),
                IRRequirement("avoid", IRAvoid("X")),
                IRRequirement("order", IROrderedVisit(("A", "B", "C"))),
                IRRequirement("deadline", IRDeadline("A", 1, 10)),
                IRRequirement("until", IRMaintainUntil("X", "C")),
                IRRequirement("on", IROn("A", IRVisit("B"))),
                IRRequirement(
                    "alternative", IRAlternative((IRVisit("A"), IRVisit("D")))
                ),
                IRRequirement("all", IRAllOf((IRVisit("A"), IRAvoid("X")))),
                IRRequirement("count", IRCountAtMost("X", 1)),
                IRRequirement("once", IROn("B", IROnce("A"))),
                IRRequirement("since", IROn("C", IRSince("SAFE", "A"))),
                IRRequirement("threshold", IRThreshold("battery", ">=", 5)),
                IRRequirement(
                    "priority", IRPriority((IRVisit("C"), IRVisit("D")))
                ),
            ),
        )
        source = encode_task(task)
        self.assertEqual(format_task(parse_task(source)), source)
        for literal in (
            'task "all-fields"',
            'require "visit"',
            'ordered("A", "B", "C")',
            'deadline("A", 1, 10)',
            'maintain_until("X", "C")',
            'on("C", since("SAFE", "A"))',
            'threshold("battery", >=, 5)',
            'priority(visit("C"), visit("D"))',
        ):
            self.assertIn(literal, source)


class InterpreterTests(unittest.TestCase):
    def test_sequence_safety_count_and_threshold(self) -> None:
        source = '''task "route" {
          require "sequence": ordered("A", "B", "C");
          require "safety": avoid("X");
          require "count": count_at_most("A", 1);
          require "power": threshold("battery", >=, 5);
        }'''
        good = [step("S", battery=9), step("A", battery=8),
                step("B", battery=7), step("C", battery=6)]
        self.assertTrue(evaluate_task(source, good))
        self.assertFalse(evaluate_task(source, good + [step("X", battery=5)]))
        self.assertFalse(evaluate_task(source, good + [step("A", battery=5)]))
        self.assertFalse(evaluate_task(source, good + [step(battery=4)]))

    def test_deadline_and_trigger_are_relative_to_each_trigger(self) -> None:
        source = '''task "reaction" {
          require "r": on("A", deadline("B", 1, 2));
        }'''
        self.assertTrue(
            evaluate_task(source, [step(), step("A"), step(), step("B")])
        )
        self.assertFalse(
            evaluate_task(source, [step("A"), step(), step(), step("B")])
        )
        self.assertTrue(evaluate_task(source, [step(), step("B")]))

    def test_once_and_since_supply_past_context_to_on(self) -> None:
        once_source = '''task "past" {
          require "r": on("B", once("A"));
        }'''
        self.assertTrue(evaluate_task(once_source, [step("A"), step(), step("B")]))
        self.assertFalse(evaluate_task(once_source, [step(), step("B"), step("A")]))

        since_source = '''task "safe-since-A" {
          require "r": on("C", since("SAFE", "A"));
        }'''
        self.assertTrue(
            evaluate_task(
                since_source,
                [step("A", "SAFE"), step("SAFE"), step("C", "SAFE")],
            )
        )
        self.assertFalse(
            evaluate_task(
                since_source,
                [step("A", "SAFE"), step(), step("C", "SAFE")],
            )
        )

    def test_maintain_until_alternative_and_all_of(self) -> None:
        source = '''task "choices" {
          require "r": all_of(
            maintain_until("X", "C"),
            alternative(visit("A"), visit("D"))
          );
        }'''
        self.assertTrue(evaluate_task(source, [step(), step("D"), step("C")]))
        self.assertFalse(evaluate_task(source, [step("X"), step("D"), step("C")]))
        self.assertFalse(evaluate_task(source, [step(), step("C")]))

    def test_priority_boolean_and_rank(self) -> None:
        task = parse_task(
            '''task "preference" {
              require "r": priority(visit("C"), visit("D"));
            }'''
        )
        expression = task.requirements[0].expression
        self.assertIsInstance(expression, Priority)
        assert isinstance(expression, Priority)
        trace = [step(), step("D"), step("C")]
        self.assertTrue(evaluate_expression(expression, trace))
        self.assertEqual(priority_rank(expression, trace), 0)
        self.assertIsNone(priority_rank(expression, [step()]))


if __name__ == "__main__":
    unittest.main()
