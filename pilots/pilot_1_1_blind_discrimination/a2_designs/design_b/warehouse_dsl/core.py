"""Parser, canonical formatter, and finite-trace interpreter for the DSL."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Union


class DSLSyntaxError(ValueError):
    """Raised when task source is not a valid program in the closed DSL."""


@dataclass(frozen=True)
class Seen:
    label: str


@dataclass(frozen=True)
class Never:
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Order:
    labels: tuple[str, ...]


@dataclass(frozen=True)
class Until:
    goal: str
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class Within:
    lower: int
    upper: int
    body: "Expression"


@dataclass(frozen=True)
class After:
    trigger: str
    body: "Expression"


@dataclass(frozen=True)
class All:
    children: tuple["Expression", ...]


@dataclass(frozen=True)
class AnyOf:
    children: tuple["Expression", ...]


Expression = Union[Seen, Never, Order, Until, Within, After, All, AnyOf]


@dataclass(frozen=True)
class Task:
    """An immutable parsed task."""

    root: Expression


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    position: int


_TOKEN = re.compile(
    r"\s*(?:(?P<INT>[0-9]+)|(?P<NAME>[A-Za-z][A-Za-z0-9_]*)|"
    r"(?P<DOTS>\.\.)|(?P<SYMBOL>[{}\[\],;]))"
)


def _tokenize(source: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            if source[position:].strip() == "":
                position = len(source)
                break
            excerpt = source[position : position + 16].splitlines()[0]
            raise DSLSyntaxError(
                f"unexpected text at character {position}: {excerpt!r}"
            )
        kind = match.lastgroup
        assert kind is not None
        tokens.append(_Token(kind, match.group(kind), match.start(kind)))
        position = match.end()
    tokens.append(_Token("EOF", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, source: str) -> None:
        self.tokens = _tokenize(source)
        self.index = 0

    def parse(self) -> Task:
        if self._peek().kind == "EOF":
            raise DSLSyntaxError("task source is empty")
        root = self._expression()
        self._expect_kind("EOF")
        return Task(root)

    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _take(self) -> _Token:
        token = self._peek()
        self.index += 1
        return token

    def _accept_text(self, text: str) -> bool:
        if self._peek().text == text:
            self.index += 1
            return True
        return False

    def _expect_text(self, text: str) -> _Token:
        token = self._peek()
        if token.text != text:
            raise DSLSyntaxError(
                f"expected {text!r} at character {token.position}, got {token.text!r}"
            )
        return self._take()

    def _expect_kind(self, kind: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            expected = "end of source" if kind == "EOF" else kind.lower()
            raise DSLSyntaxError(
                f"expected {expected} at character {token.position}, got {token.text!r}"
            )
        return self._take()

    def _label(self) -> str:
        return self._expect_kind("NAME").text

    def _label_list(self, *, allow_duplicates: bool = False) -> tuple[str, ...]:
        self._expect_text("[")
        if self._peek().text == "]":
            raise DSLSyntaxError(
                f"label list cannot be empty at character {self._peek().position}"
            )
        labels = [self._label()]
        while self._accept_text(","):
            labels.append(self._label())
        self._expect_text("]")
        if not allow_duplicates and len(set(labels)) != len(labels):
            raise DSLSyntaxError("a label list cannot contain duplicates")
        return tuple(labels)

    def _single_body(self) -> Expression:
        self._expect_text("{")
        body = self._expression()
        self._expect_text("}")
        return body

    def _many_body(self) -> tuple[Expression, ...]:
        self._expect_text("{")
        if self._peek().text == "}":
            raise DSLSyntaxError(
                f"boolean block cannot be empty at character {self._peek().position}"
            )
        children: list[Expression] = []
        while True:
            children.append(self._expression())
            if self._accept_text(";"):
                if self._accept_text("}"):
                    break
                continue
            self._expect_text("}")
            break
        return tuple(children)

    def _expression(self) -> Expression:
        construct = self._expect_kind("NAME")
        name = construct.text

        if name == "seen":
            return Seen(self._label())
        if name == "never":
            return Never(self._label_list())
        if name == "order":
            labels = self._label_list(allow_duplicates=True)
            if len(labels) < 2:
                raise DSLSyntaxError("order requires at least two labels")
            return Order(labels)
        if name == "until":
            goal = self._label()
            self._expect_text("avoiding")
            return Until(goal, self._label_list())
        if name == "within":
            lower_token = self._expect_kind("INT")
            self._expect_text("..")
            upper_token = self._expect_kind("INT")
            lower = int(lower_token.text)
            upper = int(upper_token.text)
            if lower > upper:
                raise DSLSyntaxError(
                    f"within lower bound {lower} exceeds upper bound {upper}"
                )
            return Within(lower, upper, self._single_body())
        if name == "after":
            trigger = self._label()
            return After(trigger, self._single_body())
        if name == "all":
            return All(self._many_body())
        if name == "any":
            return AnyOf(self._many_body())

        raise DSLSyntaxError(
            f"unknown construct {name!r} at character {construct.position}"
        )


def parse_task(source: str) -> Task:
    """Parse *source* and return an immutable :class:`Task` syntax tree."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    return _Parser(source).parse()


def _format(expression: Expression, level: int) -> list[str]:
    indent = "  " * level
    if isinstance(expression, Seen):
        return [f"{indent}seen {expression.label}"]
    if isinstance(expression, Never):
        return [f"{indent}never [{', '.join(expression.labels)}]"]
    if isinstance(expression, Order):
        return [f"{indent}order [{', '.join(expression.labels)}]"]
    if isinstance(expression, Until):
        labels = ", ".join(expression.forbidden)
        return [f"{indent}until {expression.goal} avoiding [{labels}]"]
    if isinstance(expression, Within):
        lines = [f"{indent}within {expression.lower}..{expression.upper} {{"]
        lines.extend(_format(expression.body, level + 1))
        lines.append(f"{indent}}}")
        return lines
    if isinstance(expression, After):
        lines = [f"{indent}after {expression.trigger} {{"]
        lines.extend(_format(expression.body, level + 1))
        lines.append(f"{indent}}}")
        return lines
    if isinstance(expression, (All, AnyOf)):
        keyword = "all" if isinstance(expression, All) else "any"
        lines = [f"{indent}{keyword} {{"]
        for child in expression.children:
            child_lines = _format(child, level + 1)
            child_lines[-1] += ";"
            lines.extend(child_lines)
        lines.append(f"{indent}}}")
        return lines
    raise TypeError(f"unsupported expression object: {type(expression).__name__}")


def canonicalize(source: str) -> str:
    """Parse *source* and return its deterministic canonical spelling."""

    task = parse_task(source)
    return "\n".join(_format(task.root, 0)) + "\n"


def _evaluate(
    expression: Expression,
    trace: tuple[frozenset[str], ...],
    start: int,
    end: int,
) -> bool:
    if isinstance(expression, Seen):
        return any(expression.label in trace[index] for index in range(start, end + 1))

    if isinstance(expression, Never):
        forbidden = frozenset(expression.labels)
        return all(trace[index].isdisjoint(forbidden) for index in range(start, end + 1))

    if isinstance(expression, Order):
        cursor = start
        for label in expression.labels:
            for index in range(cursor, end + 1):
                if label in trace[index]:
                    cursor = index + 1
                    break
            else:
                return False
        return True

    if isinstance(expression, Until):
        forbidden = frozenset(expression.forbidden)
        blocked = False
        for index in range(start, end + 1):
            step = trace[index]
            # Test the endpoint before updating blocked: forbidden labels are
            # allowed on a step that simultaneously contains the goal.
            if expression.goal in step and not blocked:
                return True
            if not step.isdisjoint(forbidden):
                blocked = True
        return False

    if isinstance(expression, Within):
        window_start = start + expression.lower
        window_end = min(start + expression.upper, end)
        return _evaluate(expression.body, trace, window_start, window_end)

    if isinstance(expression, After):
        return all(
            _evaluate(expression.body, trace, index, end)
            for index in range(start, end + 1)
            if expression.trigger in trace[index]
        )

    if isinstance(expression, All):
        return all(_evaluate(child, trace, start, end) for child in expression.children)

    if isinstance(expression, AnyOf):
        return any(_evaluate(child, trace, start, end) for child in expression.children)

    raise TypeError(f"unsupported expression object: {type(expression).__name__}")


def _validate_trace(trace: tuple[frozenset[str], ...]) -> None:
    if not isinstance(trace, tuple):
        raise TypeError("trace must be a tuple of frozenset steps")
    for index, step in enumerate(trace):
        if not isinstance(step, frozenset):
            raise TypeError(f"trace step {index} must be a frozenset")
        if not all(isinstance(label, str) for label in step):
            raise TypeError(f"trace step {index} contains a non-string label")


def evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool:
    """Evaluate a task source against a finite trace and return a Boolean."""

    task = parse_task(source)
    _validate_trace(trace)
    return _evaluate(task.root, trace, 0, len(trace) - 1)
