"""Parser, canonical formatter, and finite-trace interpreter."""

from __future__ import annotations

from dataclasses import dataclass
import re


_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
_INTEGER = re.compile(r"[0-9]+\Z")
_MAX_SOURCE_LENGTH = 100_000
_MAX_NESTING = 128


class DSLParseError(ValueError):
    """Raised when task source does not belong to the closed grammar."""


@dataclass(frozen=True)
class Task:
    """An immutable, parsed task node.

    ``kind`` is one of the documented closed constructs. ``args`` contains
    labels, integer bounds, or child ``Task`` nodes as appropriate.
    """

    kind: str
    args: tuple[object, ...]


@dataclass(frozen=True)
class _Token:
    text: str
    line: int
    column: int


def _tokens(source: str) -> list[_Token]:
    result: list[_Token] = []
    index = 0
    line = 1
    column = 1
    length = len(source)

    while index < length:
        character = source[index]
        if character.isspace():
            if character == "\n":
                line += 1
                column = 1
            else:
                column += 1
            index += 1
            continue

        if character in "()":
            result.append(_Token(character, line, column))
            index += 1
            column += 1
            continue

        start = index
        start_column = column
        while index < length and not source[index].isspace() and source[index] not in "()":
            index += 1
            column += 1
        result.append(_Token(source[start:index], line, start_column))

    return result


class _Parser:
    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.position = 0

    def error(self, message: str, token: _Token | None = None) -> DSLParseError:
        if token is None:
            if self.tokens:
                last = self.tokens[-1]
                return DSLParseError(
                    f"{message} at end of source after line {last.line}, column {last.column}"
                )
            return DSLParseError(f"{message} at end of empty source")
        return DSLParseError(f"{message} at line {token.line}, column {token.column}")

    def take(self) -> _Token:
        if self.position >= len(self.tokens):
            raise self.error("unexpected end of source")
        token = self.tokens[self.position]
        self.position += 1
        return token

    def expression(self, depth: int = 0) -> Task:
        if depth > _MAX_NESTING:
            token = self.tokens[self.position] if self.position < len(self.tokens) else None
            raise self.error(f"nesting exceeds {_MAX_NESTING}", token)

        opening = self.take()
        if opening.text != "(":
            raise self.error("expected '(' to start a task construct", opening)

        operator = self.take()
        if operator.text in ("(", ")"):
            raise self.error("expected a construct name", operator)

        if operator.text == "eventually":
            node = Task(operator.text, (self.label(),))
        elif operator.text == "never":
            node = Task(operator.text, (self.label(),))
        elif operator.text == "sequence":
            labels: list[str] = []
            while self.peek_text() != ")":
                labels.append(self.label())
            if len(labels) < 2:
                raise self.error("'sequence' requires at least two labels", operator)
            node = Task(operator.text, tuple(labels))
        elif operator.text == "within":
            lower = self.integer()
            upper = self.integer()
            label = self.label()
            if lower > upper:
                raise self.error("'within' lower bound must not exceed upper bound", operator)
            node = Task(operator.text, (lower, upper, label))
        elif operator.text == "avoid-until":
            node = Task(operator.text, (self.label(), self.label()))
        elif operator.text == "after-each":
            trigger = self.label()
            child = self.expression(depth + 1)
            node = Task(operator.text, (trigger, child))
        elif operator.text in ("all", "any"):
            children: list[Task] = []
            while self.peek_text() != ")":
                children.append(self.expression(depth + 1))
            if len(children) < 2:
                raise self.error(f"'{operator.text}' requires at least two child tasks", operator)
            node = Task(operator.text, tuple(children))
        else:
            raise self.error(f"unknown construct {operator.text!r}", operator)

        closing = self.take()
        if closing.text != ")":
            raise self.error(f"too many arguments to '{operator.text}'", closing)
        return node

    def peek_text(self) -> str | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position].text

    def label(self) -> str:
        token = self.take()
        if not _LABEL.fullmatch(token.text):
            raise self.error(
                "expected a label matching [A-Za-z_][A-Za-z0-9_.-]*", token
            )
        return token.text

    def integer(self) -> int:
        token = self.take()
        if not _INTEGER.fullmatch(token.text):
            raise self.error("expected a nonnegative decimal integer", token)
        return int(token.text)


def parse_task(source: str) -> Task:
    """Parse exactly one closed-DSL task and return its immutable AST."""

    if not isinstance(source, str):
        raise TypeError("source must be a str")
    if len(source) > _MAX_SOURCE_LENGTH:
        raise DSLParseError(f"source exceeds {_MAX_SOURCE_LENGTH} characters")

    parser = _Parser(_tokens(source))
    task = parser.expression()
    if parser.position != len(parser.tokens):
        token = parser.tokens[parser.position]
        raise parser.error("expected end of source after one task", token)
    return task


def _canonical(task: Task) -> str:
    if task.kind in ("eventually", "never"):
        return f"({task.kind} {task.args[0]})"
    if task.kind == "sequence":
        return f"(sequence {' '.join(task.args)})"
    if task.kind == "within":
        lower, upper, label = task.args
        return f"(within {lower} {upper} {label})"
    if task.kind == "avoid-until":
        avoided, goal = task.args
        return f"(avoid-until {avoided} {goal})"
    if task.kind == "after-each":
        trigger, child = task.args
        return f"(after-each {trigger} {_canonical(child)})"
    if task.kind in ("all", "any"):
        return f"({task.kind} {' '.join(_canonical(child) for child in task.args)})"
    raise AssertionError(f"unreachable task kind {task.kind!r}")


def canonicalize(source: str) -> str:
    """Return the unique one-line spelling of a valid task source."""

    return _canonical(parse_task(source))


def _validate_trace(trace: tuple[frozenset[str], ...]) -> None:
    if not isinstance(trace, tuple):
        raise TypeError("trace must be a tuple")
    for index, step in enumerate(trace):
        if not isinstance(step, frozenset):
            raise TypeError(f"trace step {index} must be a frozenset")
        for label in step:
            if not isinstance(label, str):
                raise TypeError(f"trace step {index} contains a non-str label")


def _satisfies(task: Task, trace: tuple[frozenset[str], ...], origin: int) -> bool:
    kind = task.kind

    if kind == "eventually":
        label = task.args[0]
        return any(label in trace[index] for index in range(origin, len(trace)))

    if kind == "never":
        label = task.args[0]
        return all(label not in trace[index] for index in range(origin, len(trace)))

    if kind == "sequence":
        next_index = origin
        for label in task.args:
            while next_index < len(trace) and label not in trace[next_index]:
                next_index += 1
            if next_index == len(trace):
                return False
            next_index += 1
        return True

    if kind == "within":
        lower, upper, label = task.args
        first = origin + lower
        last = min(origin + upper, len(trace) - 1)
        return first <= last and any(label in trace[index] for index in range(first, last + 1))

    if kind == "avoid-until":
        avoided, goal = task.args
        for endpoint in range(origin, len(trace)):
            if goal in trace[endpoint]:
                return all(avoided not in trace[index] for index in range(origin, endpoint))
        return False

    if kind == "after-each":
        trigger, child = task.args
        return all(
            _satisfies(child, trace, index)
            for index in range(origin, len(trace))
            if trigger in trace[index]
        )

    if kind == "all":
        return all(_satisfies(child, trace, origin) for child in task.args)

    if kind == "any":
        return any(_satisfies(child, trace, origin) for child in task.args)

    raise AssertionError(f"unreachable task kind {kind!r}")


def evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool:
    """Parse and evaluate ``source`` on a finite trace from index zero."""

    task = parse_task(source)
    _validate_trace(trace)
    return _satisfies(task, trace, 0)
