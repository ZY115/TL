"""Closed, deterministic parser and canonical formatter for WTL."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .model import (
    AllOf,
    Alternative,
    Avoid,
    CountAtMost,
    Deadline,
    Expression,
    MaintainUntil,
    On,
    Once,
    Ordered,
    Priority,
    Requirement,
    Since,
    Task,
    TaskExpression,
    Threshold,
    Visit,
)


class WTLParseError(ValueError):
    """A syntax error with a deterministic source location."""


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str | int
    offset: int


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)")


def _location(source: str, offset: int) -> str:
    line = source.count("\n", 0, offset) + 1
    last_newline = source.rfind("\n", 0, offset)
    column = offset - last_newline
    return f"line {line}, column {column}"


def _tokenize(source: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0
    decoder = json.JSONDecoder()
    while index < len(source):
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character in "{}(),:;":
            tokens.append(_Token(character, character, index))
            index += 1
            continue
        if character == '"':
            try:
                value, end = decoder.raw_decode(source, index)
            except json.JSONDecodeError as exc:
                raise WTLParseError(
                    f"invalid string at {_location(source, index)}"
                ) from exc
            if not isinstance(value, str):  # defensive: raw_decode began at a quote
                raise WTLParseError(f"expected string at {_location(source, index)}")
            tokens.append(_Token("STRING", value, index))
            index = end
            continue
        identifier = _IDENTIFIER.match(source, index)
        if identifier:
            tokens.append(_Token("IDENT", identifier.group(0), index))
            index = identifier.end()
            continue
        if source.startswith(("<=", ">=", "=="), index):
            tokens.append(_Token("OP", source[index : index + 2], index))
            index += 2
            continue
        if character in "<>":
            tokens.append(_Token("OP", character, index))
            index += 1
            continue
        integer = _INTEGER.match(source, index)
        if integer:
            tokens.append(_Token("INT", int(integer.group(0)), index))
            index = integer.end()
            continue
        raise WTLParseError(
            f"unexpected character {character!r} at {_location(source, index)}"
        )
    tokens.append(_Token("EOF", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, source: str):
        self.source = source
        self.tokens = _tokenize(source)
        self.cursor = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.cursor]

    def fail(self, message: str) -> WTLParseError:
        return WTLParseError(
            f"{message} at {_location(self.source, self.current.offset)}"
        )

    def accept(self, kind: str, value: str | None = None) -> _Token | None:
        token = self.current
        if token.kind == kind and (value is None or token.value == value):
            self.cursor += 1
            return token
        return None

    def expect(self, kind: str, value: str | None = None) -> _Token:
        token = self.accept(kind, value)
        if token is None:
            expected = repr(value) if value is not None else kind.lower()
            raise self.fail(f"expected {expected}")
        return token

    def keyword(self, value: str) -> None:
        self.expect("IDENT", value)

    def string(self) -> str:
        return str(self.expect("STRING").value)

    def integer(self) -> int:
        return int(self.expect("INT").value)

    def comma(self) -> None:
        self.expect(",")

    def parse_task(self) -> Task:
        self.keyword("task")
        task_id = self.string()
        self.expect("{")
        requirements: list[Requirement] = []
        while not self.accept("}"):
            if self.current.kind == "EOF":
                raise self.fail("expected requirement or '}'")
            self.keyword("require")
            requirement_id = self.string()
            self.expect(":")
            expression = self.expression()
            self.expect(";")
            requirements.append(Requirement(requirement_id, expression))
        self.expect("EOF")
        try:
            return Task(task_id, tuple(requirements))
        except (TypeError, ValueError) as exc:
            raise WTLParseError(str(exc)) from exc

    def expression(self) -> TaskExpression:
        name = str(self.expect("IDENT").value)
        self.expect("(")
        try:
            expression = self._expression_body(name)
        except (TypeError, ValueError) as exc:
            raise self.fail(str(exc)) from exc
        self.expect(")")
        return expression

    def _expression_body(self, name: str) -> TaskExpression:
        if name == "visit":
            return Visit(self.string())
        if name == "avoid":
            return Avoid(self.string())
        if name == "ordered":
            return Ordered(self._string_list())
        if name == "deadline":
            event = self.string()
            self.comma()
            lower = self.integer()
            self.comma()
            return Deadline(event, lower, self.integer())
        if name == "maintain_until":
            forbidden = self.string()
            self.comma()
            return MaintainUntil(forbidden, self.string())
        if name == "on":
            trigger = self.string()
            self.comma()
            return On(trigger, self.expression())
        if name == "alternative":
            return Alternative(self._expression_list())
        if name == "all_of":
            return AllOf(self._expression_list())
        if name == "count_at_most":
            event = self.string()
            self.comma()
            return CountAtMost(event, self.integer())
        if name == "once":
            return Once(self.string())
        if name == "since":
            condition = self.string()
            self.comma()
            return Since(condition, self.string())
        if name == "threshold":
            resource = self.string()
            self.comma()
            operator = str(self.expect("OP").value)
            self.comma()
            return Threshold(resource, operator, self.integer())
        if name == "priority":
            return Priority(self._expression_list())
        raise self.fail(f"unknown WTL construct {name!r}")

    def _string_list(self) -> tuple[str, ...]:
        values = [self.string()]
        while self.accept(","):
            values.append(self.string())
        return tuple(values)

    def _expression_list(self) -> tuple[Expression, ...]:
        values: list[Expression] = [self.expression()]
        while self.accept(","):
            values.append(self.expression())
        return tuple(values)


def parse_task(source: str) -> Task:
    """Parse exactly one WTL task; trailing input is rejected."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    return _Parser(source).parse_task()


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def format_expression(expression: TaskExpression) -> str:
    """Return the unique canonical spelling of an expression."""

    if isinstance(expression, Visit):
        return f"visit({_quoted(expression.event)})"
    if isinstance(expression, Avoid):
        return f"avoid({_quoted(expression.event)})"
    if isinstance(expression, Ordered):
        return f"ordered({', '.join(map(_quoted, expression.events))})"
    if isinstance(expression, Deadline):
        return f"deadline({_quoted(expression.event)}, {expression.lower}, {expression.upper})"
    if isinstance(expression, MaintainUntil):
        return (
            f"maintain_until({_quoted(expression.forbidden)}, "
            f"{_quoted(expression.goal)})"
        )
    if isinstance(expression, On):
        return f"on({_quoted(expression.trigger)}, {format_expression(expression.obligation)})"
    if isinstance(expression, Alternative):
        body = ", ".join(format_expression(item) for item in expression.options)
        return f"alternative({body})"
    if isinstance(expression, AllOf):
        body = ", ".join(format_expression(item) for item in expression.requirements)
        return f"all_of({body})"
    if isinstance(expression, CountAtMost):
        return f"count_at_most({_quoted(expression.event)}, {expression.maximum})"
    if isinstance(expression, Once):
        return f"once({_quoted(expression.event)})"
    if isinstance(expression, Since):
        return f"since({_quoted(expression.condition)}, {_quoted(expression.landmark)})"
    if isinstance(expression, Threshold):
        return (
            f"threshold({_quoted(expression.resource)}, {expression.operator}, "
            f"{expression.value})"
        )
    if isinstance(expression, Priority):
        body = ", ".join(format_expression(item) for item in expression.options)
        return f"priority({body})"
    raise TypeError(f"unsupported WTL expression: {type(expression)!r}")


def format_task(task: Task) -> str:
    """Serialize a task canonically, with one requirement per line."""

    if not isinstance(task, Task):
        raise TypeError("task must be a WTL Task")
    lines = [f"task {_quoted(task.id)} {{"]
    lines.extend(
        f"  require {_quoted(requirement.id)}: "
        f"{format_expression(requirement.expression)};"
        for requirement in task.requirements
    )
    lines.append("}")
    return "\n".join(lines) + "\n"
