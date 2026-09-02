"""Parser, formatter, and finite-trace interpreter for Warehouse DSL.

The implementation is deliberately self-contained and uses no dynamic code
execution.  Task sources can only construct one of the node types declared in
this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Union


LABEL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z", re.ASCII)
MAX_SOURCE_LENGTH = 100_000
MAX_NESTING = 64
MAX_NODES = 10_000
MAX_BOUND = 1_000_000_000


class DSLParseError(ValueError):
    """Raised when a task source is not valid Warehouse DSL."""


@dataclass(frozen=True)
class Visit:
    label: str


@dataclass(frozen=True)
class Avoid:
    label: str


@dataclass(frozen=True)
class Sequence:
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Between:
    minimum: int
    maximum: int
    label: str


@dataclass(frozen=True)
class AvoidUntil:
    forbidden: str
    goal: str


@dataclass(frozen=True)
class AfterEach:
    trigger: str
    requirement: "Expr"


@dataclass(frozen=True)
class AllOf:
    requirements: tuple["Expr", ...]


@dataclass(frozen=True)
class AnyOf:
    alternatives: tuple["Expr", ...]


Expr = Union[Visit, Avoid, Sequence, Between, AvoidUntil, AfterEach, AllOf, AnyOf]


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


def _location(source: str, position: int) -> str:
    line = source.count("\n", 0, position) + 1
    last_newline = source.rfind("\n", 0, position)
    column = position - last_newline
    return f"line {line}, column {column}"


def _tokenize(source: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    index = 0
    while index < len(source):
        if source[index].isspace():
            index += 1
            continue
        start = index
        character = source[index]
        if character in "(),":
            kind = {"(": "LPAREN", ")": "RPAREN", ",": "COMMA"}[character]
            tokens.append(_Token(kind, character, start))
            index += 1
            continue
        name_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[index:], re.ASCII)
        if name_match is not None:
            value = name_match.group(0)
            tokens.append(_Token("NAME", value, start))
            index += len(value)
            continue
        integer_match = re.match(r"[0-9]+", source[index:], re.ASCII)
        if integer_match is not None:
            value = integer_match.group(0)
            tokens.append(_Token("INT", value, start))
            index += len(value)
            continue
        raise DSLParseError(
            f"unexpected character {character!r} at {_location(source, start)}"
        )
    tokens.append(_Token("EOF", "", len(source)))
    return tuple(tokens)


class _Parser:
    _CONSTRUCTS = {
        "visit",
        "avoid",
        "sequence",
        "between",
        "avoid_until",
        "after_each",
        "all",
        "any",
    }

    def __init__(self, source: str):
        self.source = source
        self.tokens = _tokenize(source)
        self.index = 0
        self.node_count = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def error(self, message: str, token: Optional[_Token] = None) -> DSLParseError:
        selected = token if token is not None else self.current
        return DSLParseError(
            f"{message} at {_location(self.source, selected.position)}"
        )

    def take(self, kind: str) -> _Token:
        token = self.current
        if token.kind != kind:
            display = "end of source" if token.kind == "EOF" else repr(token.value)
            raise self.error(f"expected {kind.lower()}, found {display}", token)
        self.index += 1
        return token

    def accept(self, kind: str) -> bool:
        if self.current.kind == kind:
            self.index += 1
            return True
        return False

    def parse_label(self) -> str:
        token = self.take("NAME")
        # Tokenization already enforces LABEL_RE; retain this assertion as a
        # local invariant if the tokenizer is changed later.
        if LABEL_RE.fullmatch(token.value) is None:
            raise self.error("invalid proposition label", token)
        return token.value

    def parse_bound(self) -> int:
        token = self.take("INT")
        if len(token.value) > 10:
            raise self.error(f"bound exceeds {MAX_BOUND}", token)
        value = int(token.value)
        if value > MAX_BOUND:
            raise self.error(f"bound exceeds {MAX_BOUND}", token)
        return value

    def parse(self) -> Expr:
        if self.current.kind == "EOF":
            raise self.error("task source is empty")
        expression = self.parse_expr(depth=1)
        if self.current.kind != "EOF":
            raise self.error(f"unexpected trailing token {self.current.value!r}")
        return expression

    def parse_expr(self, depth: int) -> Expr:
        if depth > MAX_NESTING:
            raise self.error(f"nesting exceeds {MAX_NESTING}")
        self.node_count += 1
        if self.node_count > MAX_NODES:
            raise self.error(f"task exceeds {MAX_NODES} expression nodes")

        name_token = self.take("NAME")
        name = name_token.value
        if name not in self._CONSTRUCTS:
            raise self.error(f"unknown construct {name!r}", name_token)
        self.take("LPAREN")

        if name == "visit":
            expression: Expr = Visit(self.parse_label())
        elif name == "avoid":
            expression = Avoid(self.parse_label())
        elif name == "sequence":
            labels = self.parse_label_list()
            if len(labels) < 2:
                raise self.error("sequence requires at least two labels", name_token)
            expression = Sequence(labels)
        elif name == "between":
            minimum = self.parse_bound()
            self.take("COMMA")
            maximum = self.parse_bound()
            self.take("COMMA")
            label = self.parse_label()
            if minimum > maximum:
                raise self.error(
                    "between lower bound must not exceed upper bound", name_token
                )
            expression = Between(minimum, maximum, label)
        elif name == "avoid_until":
            forbidden = self.parse_label()
            self.take("COMMA")
            goal = self.parse_label()
            expression = AvoidUntil(forbidden, goal)
        elif name == "after_each":
            trigger = self.parse_label()
            self.take("COMMA")
            requirement = self.parse_expr(depth + 1)
            expression = AfterEach(trigger, requirement)
        elif name in {"all", "any"}:
            requirements = self.parse_expr_list(depth + 1)
            if len(requirements) < 2:
                raise self.error(f"{name} requires at least two arguments", name_token)
            expression = (
                AllOf(requirements) if name == "all" else AnyOf(requirements)
            )
        else:  # pragma: no cover - exhaustive guard for future edits
            raise AssertionError(f"unhandled construct: {name}")

        self.take("RPAREN")
        return expression

    def parse_label_list(self) -> tuple[str, ...]:
        labels = [self.parse_label()]
        while self.accept("COMMA"):
            labels.append(self.parse_label())
        return tuple(labels)

    def parse_expr_list(self, depth: int) -> tuple[Expr, ...]:
        requirements = [self.parse_expr(depth)]
        while self.accept("COMMA"):
            requirements.append(self.parse_expr(depth))
        return tuple(requirements)


def parse_task(source: str) -> Expr:
    """Parse *source* into an immutable, closed Warehouse DSL syntax tree."""

    if not isinstance(source, str):
        raise TypeError("source must be a str")
    if len(source) > MAX_SOURCE_LENGTH:
        raise DSLParseError(f"source exceeds {MAX_SOURCE_LENGTH} characters")
    return _Parser(source).parse()


def _format(expression: Expr) -> str:
    if isinstance(expression, Visit):
        return f"visit({expression.label})"
    if isinstance(expression, Avoid):
        return f"avoid({expression.label})"
    if isinstance(expression, Sequence):
        return f"sequence({', '.join(expression.labels)})"
    if isinstance(expression, Between):
        return (
            f"between({expression.minimum}, {expression.maximum}, "
            f"{expression.label})"
        )
    if isinstance(expression, AvoidUntil):
        return f"avoid_until({expression.forbidden}, {expression.goal})"
    if isinstance(expression, AfterEach):
        return f"after_each({expression.trigger}, {_format(expression.requirement)})"
    if isinstance(expression, AllOf):
        return f"all({', '.join(_format(item) for item in expression.requirements)})"
    if isinstance(expression, AnyOf):
        return f"any({', '.join(_format(item) for item in expression.alternatives)})"
    raise TypeError(f"unsupported expression node: {type(expression).__name__}")


def canonicalize(source: str) -> str:
    """Validate *source* and return its deterministic single-line spelling."""

    return _format(parse_task(source))


def _validate_trace(trace: tuple[frozenset[str], ...]) -> None:
    if not isinstance(trace, tuple):
        raise TypeError("trace must be a tuple")
    for index, step in enumerate(trace):
        if not isinstance(step, frozenset):
            raise TypeError(f"trace step {index} must be a frozenset")
        for label in step:
            if not isinstance(label, str):
                raise TypeError(f"trace step {index} contains a non-str label")


def _evaluate(expression: Expr, trace: tuple[frozenset[str], ...], anchor: int) -> bool:
    if isinstance(expression, Visit):
        return any(expression.label in trace[index] for index in range(anchor, len(trace)))

    if isinstance(expression, Avoid):
        return all(expression.label not in trace[index] for index in range(anchor, len(trace)))

    if isinstance(expression, Sequence):
        next_index = anchor
        for label in expression.labels:
            while next_index < len(trace) and label not in trace[next_index]:
                next_index += 1
            if next_index == len(trace):
                return False
            # Consuming the selected position enforces strict increase, even
            # when one step contains several requested labels.
            next_index += 1
        return True

    if isinstance(expression, Between):
        first = anchor + expression.minimum
        last = min(anchor + expression.maximum, len(trace) - 1)
        if first > last:
            return False
        return any(expression.label in trace[index] for index in range(first, last + 1))

    if isinstance(expression, AvoidUntil):
        for goal_index in range(anchor, len(trace)):
            if expression.goal in trace[goal_index]:
                if all(
                    expression.forbidden not in trace[index]
                    for index in range(anchor, goal_index)
                ):
                    return True
        return False

    if isinstance(expression, AfterEach):
        return all(
            _evaluate(expression.requirement, trace, index)
            for index in range(anchor, len(trace))
            if expression.trigger in trace[index]
        )

    if isinstance(expression, AllOf):
        return all(_evaluate(item, trace, anchor) for item in expression.requirements)

    if isinstance(expression, AnyOf):
        return any(_evaluate(item, trace, anchor) for item in expression.alternatives)

    raise TypeError(f"unsupported expression node: {type(expression).__name__}")


def evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool:
    """Return the finite-trace Boolean denoted by *source* on *trace*."""

    expression = parse_task(source)
    _validate_trace(trace)
    return _evaluate(expression, trace, anchor=0)
