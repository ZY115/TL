"""Closed, compositional task DSL for finite warehouse traces.

The public entry point is :func:`evaluate_task`.  Parsing is implemented by a
small lexer/parser; task source is never executed as Python or translated to an
executable general-purpose language.
"""

from __future__ import annotations

import json
import operator
import re
from collections.abc import Sequence, Set
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeAlias

if TYPE_CHECKING:
    from neutral_ir.schema import TaskSpec as NeutralTaskSpec
else:
    NeutralTaskSpec = object


DESIGN_SEED = 1101


class TaskSourceError(ValueError):
    """Raised when task source is not in the closed DSL grammar."""


class Expr:
    """Marker base class for the DSL's fixed set of task expressions."""


@dataclass(frozen=True, slots=True)
class Visit(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Avoid(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class OrderedVisit(Expr):
    events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Deadline(Expr):
    event: str
    lower: int
    upper: int


@dataclass(frozen=True, slots=True)
class MaintainUntil(Expr):
    forbidden: str
    goal: str


@dataclass(frozen=True, slots=True)
class On(Expr):
    trigger: str
    obligation: Expr


@dataclass(frozen=True, slots=True)
class Alternative(Expr):
    options: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class AllOf(Expr):
    requirements: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class CountAtMost(Expr):
    event: str
    maximum: int


@dataclass(frozen=True, slots=True)
class Once(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Since(Expr):
    condition: str
    landmark: str


@dataclass(frozen=True, slots=True)
class Threshold(Expr):
    resource: str
    comparison: str
    value: int


@dataclass(frozen=True, slots=True)
class Priority(Expr):
    options: tuple[Expr, ...]


Expression: TypeAlias = (
    Visit
    | Avoid
    | OrderedVisit
    | Deadline
    | MaintainUntil
    | On
    | Alternative
    | AllOf
    | CountAtMost
    | Once
    | Since
    | Threshold
    | Priority
)


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    expression: Expression


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    requirements: tuple[Requirement, ...]


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    offset: int


_TOKEN = re.compile(
    r"(?P<space>\s+)"
    r"|(?P<comment>\#[^\r\n]*)"
    r'|(?P<string>"(?:\\.|[^"\\])*")'
    r"|(?P<number>-(?:0|[1-9][0-9]*)|0|[1-9][0-9]*)"
    r"|(?P<comparison><=|>=|==|<|>)"
    r"|(?P<identifier>[A-Za-z_][A-Za-z0-9_-]*)"
    r"|(?P<punctuation>[{}(),;=])"
)


def _location(source: str, offset: int) -> str:
    line = source.count("\n", 0, offset) + 1
    previous_newline = source.rfind("\n", 0, offset)
    column = offset - previous_newline
    return f"line {line}, column {column}"


def _lex(source: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    offset = 0
    while offset < len(source):
        match = _TOKEN.match(source, offset)
        if match is None:
            raise TaskSourceError(
                f"Unexpected character {source[offset]!r} at "
                f"{_location(source, offset)}"
            )
        kind = match.lastgroup
        assert kind is not None
        if kind not in {"space", "comment"}:
            value = match.group()
            if kind == "string":
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as error:
                    raise TaskSourceError(
                        f"Invalid quoted string at {_location(source, offset)}"
                    ) from error
            tokens.append(_Token(kind, value, offset))
        offset = match.end()
    tokens.append(_Token("eof", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, source: str):
        self.source = source
        self.tokens = _lex(source)
        self.cursor = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.cursor]

    def _accept(self, kind: str, value: str | None = None) -> _Token | None:
        token = self.current
        if token.kind == kind and (value is None or token.value == value):
            self.cursor += 1
            return token
        return None

    def _expect(self, kind: str, value: str | None = None) -> _Token:
        token = self._accept(kind, value)
        if token is not None:
            return token
        wanted = repr(value) if value is not None else kind
        actual = self.current.value or self.current.kind
        raise TaskSourceError(
            f"Expected {wanted}, found {actual!r} at "
            f"{_location(self.source, self.current.offset)}"
        )

    def _string(self, role: str) -> str:
        token = self._expect("string")
        if not token.value:
            raise TaskSourceError(
                f"{role} cannot be empty at "
                f"{_location(self.source, token.offset)}"
            )
        return token.value

    def _integer(self) -> int:
        return int(self._expect("number").value)

    def parse(self) -> Task:
        self._expect("identifier", "task")
        task_id = self._string("task id")
        self._expect("punctuation", "{")
        requirements: list[Requirement] = []
        seen_ids: set[str] = set()
        while not self._accept("punctuation", "}"):
            self._expect("identifier", "require")
            requirement_id = self._string("requirement id")
            if requirement_id in seen_ids:
                raise TaskSourceError(
                    f"Duplicate requirement id {requirement_id!r} at "
                    f"{_location(self.source, self.current.offset)}"
                )
            seen_ids.add(requirement_id)
            self._expect("punctuation", "=")
            requirements.append(Requirement(requirement_id, self._expression()))
            self._expect("punctuation", ";")
            if self.current.kind == "eof":
                self._expect("punctuation", "}")
        self._expect("eof")
        if not requirements:
            raise TaskSourceError("A task must contain at least one requirement")
        return Task(task_id, tuple(requirements))

    def _expression(self) -> Expression:
        function = self._expect("identifier").value
        self._expect("punctuation", "(")

        if function == "visit":
            expression: Expression = Visit(self._string("event"))
        elif function == "avoid":
            expression = Avoid(self._string("event"))
        elif function == "ordered_visit":
            expression = OrderedVisit(self._string_arguments("event"))
            return expression
        elif function == "deadline":
            event = self._string("event")
            self._expect("punctuation", ",")
            lower = self._integer()
            self._expect("punctuation", ",")
            upper = self._integer()
            expression = Deadline(event, lower, upper)
        elif function == "maintain_until":
            forbidden = self._string("forbidden event")
            self._expect("punctuation", ",")
            goal = self._string("goal event")
            expression = MaintainUntil(forbidden, goal)
        elif function == "on":
            trigger = self._string("trigger")
            self._expect("punctuation", ",")
            expression = On(trigger, self._expression())
        elif function == "alternative":
            expression = Alternative(self._expression_arguments())
            return expression
        elif function == "all_of":
            expression = AllOf(self._expression_arguments())
            return expression
        elif function == "count_at_most":
            event = self._string("event")
            self._expect("punctuation", ",")
            expression = CountAtMost(event, self._integer())
        elif function == "once":
            expression = Once(self._string("event"))
        elif function == "since":
            condition = self._string("condition")
            self._expect("punctuation", ",")
            landmark = self._string("landmark")
            expression = Since(condition, landmark)
        elif function == "threshold":
            resource = self._string("resource")
            self._expect("punctuation", ",")
            comparison = self._expect("comparison").value
            self._expect("punctuation", ",")
            expression = Threshold(resource, comparison, self._integer())
        elif function == "priority":
            expression = Priority(self._expression_arguments())
            return expression
        else:
            raise TaskSourceError(
                f"Unknown task function {function!r} at "
                f"{_location(self.source, self.current.offset)}"
            )

        self._expect("punctuation", ")")
        _validate_expression(expression)
        return expression

    def _string_arguments(self, role: str) -> tuple[str, ...]:
        if self._accept("punctuation", ")"):
            raise TaskSourceError("ordered_visit requires at least one event")
        values = [self._string(role)]
        while self._accept("punctuation", ","):
            values.append(self._string(role))
        self._expect("punctuation", ")")
        return tuple(values)

    def _expression_arguments(self) -> tuple[Expression, ...]:
        if self._accept("punctuation", ")"):
            raise TaskSourceError("Combinators require at least one expression")
        values = [self._expression()]
        while self._accept("punctuation", ","):
            values.append(self._expression())
        self._expect("punctuation", ")")
        return tuple(values)


def _validate_expression(expression: Expression) -> None:
    string_values: tuple[str, ...]
    if isinstance(expression, (Visit, Avoid, Once)):
        string_values = (expression.event,)
    elif isinstance(expression, OrderedVisit):
        if not expression.events:
            raise ValueError("ordered_visit requires at least one event")
        string_values = expression.events
    elif isinstance(expression, Deadline):
        string_values = (expression.event,)
        if expression.lower < 0 or expression.upper < expression.lower:
            raise ValueError("deadline bounds require 0 <= lower <= upper")
    elif isinstance(expression, MaintainUntil):
        string_values = (expression.forbidden, expression.goal)
    elif isinstance(expression, On):
        string_values = (expression.trigger,)
        _validate_expression(expression.obligation)  # type: ignore[arg-type]
    elif isinstance(expression, (Alternative, Priority)):
        if not expression.options:
            raise ValueError("Combinators require at least one expression")
        string_values = ()
        for option in expression.options:
            _validate_expression(option)  # type: ignore[arg-type]
    elif isinstance(expression, AllOf):
        if not expression.requirements:
            raise ValueError("Combinators require at least one expression")
        string_values = ()
        for requirement in expression.requirements:
            _validate_expression(requirement)  # type: ignore[arg-type]
    elif isinstance(expression, CountAtMost):
        string_values = (expression.event,)
        if expression.maximum < 0:
            raise ValueError("count_at_most maximum must be nonnegative")
    elif isinstance(expression, Since):
        string_values = (expression.condition, expression.landmark)
    elif isinstance(expression, Threshold):
        string_values = (expression.resource,)
        if expression.comparison not in _COMPARISONS:
            raise ValueError(f"Unsupported comparison: {expression.comparison}")
    else:
        raise TypeError(f"Unsupported expression node: {type(expression)!r}")
    if any(not value for value in string_values):
        raise ValueError("Event, condition, and resource names cannot be empty")


def validate_task(task: Task) -> None:
    """Validate a programmatically constructed task."""

    if not task.id:
        raise ValueError("task id cannot be empty")
    if not task.requirements:
        raise ValueError("A task must contain at least one requirement")
    ids = [requirement.id for requirement in task.requirements]
    if any(not requirement_id for requirement_id in ids):
        raise ValueError("requirement id cannot be empty")
    if len(set(ids)) != len(ids):
        raise ValueError("requirement ids must be unique")
    for requirement in task.requirements:
        _validate_expression(requirement.expression)


def parse_task(source: str) -> Task:
    """Parse DSL source into the fixed task AST."""

    try:
        task = _Parser(source).parse()
        validate_task(task)
        return task
    except TaskSourceError:
        raise
    except ValueError as error:
        raise TaskSourceError(str(error)) from error


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _format_expression(expression: Expression) -> str:
    if isinstance(expression, Visit):
        return f"visit({_quote(expression.event)})"
    if isinstance(expression, Avoid):
        return f"avoid({_quote(expression.event)})"
    if isinstance(expression, OrderedVisit):
        return "ordered_visit(" + ", ".join(map(_quote, expression.events)) + ")"
    if isinstance(expression, Deadline):
        return (
            f"deadline({_quote(expression.event)}, {expression.lower}, "
            f"{expression.upper})"
        )
    if isinstance(expression, MaintainUntil):
        return (
            f"maintain_until({_quote(expression.forbidden)}, "
            f"{_quote(expression.goal)})"
        )
    if isinstance(expression, On):
        return f"on({_quote(expression.trigger)}, {_format_expression(expression.obligation)})"  # type: ignore[arg-type]
    if isinstance(expression, Alternative):
        return "alternative(" + ", ".join(
            _format_expression(item) for item in expression.options
        ) + ")"
    if isinstance(expression, AllOf):
        return "all_of(" + ", ".join(
            _format_expression(item) for item in expression.requirements
        ) + ")"
    if isinstance(expression, CountAtMost):
        return f"count_at_most({_quote(expression.event)}, {expression.maximum})"
    if isinstance(expression, Once):
        return f"once({_quote(expression.event)})"
    if isinstance(expression, Since):
        return f"since({_quote(expression.condition)}, {_quote(expression.landmark)})"
    if isinstance(expression, Threshold):
        return (
            f"threshold({_quote(expression.resource)}, {expression.comparison}, "
            f"{expression.value})"
        )
    if isinstance(expression, Priority):
        return "priority(" + ", ".join(
            _format_expression(item) for item in expression.options
        ) + ")"
    raise TypeError(f"Unsupported expression node: {type(expression)!r}")


def format_task(task: Task) -> str:
    """Return the unique canonical source representation of ``task``."""

    validate_task(task)
    lines = [f"task {_quote(task.id)} {{"]
    lines.extend(
        f"  require {_quote(requirement.id)} = "
        f"{_format_expression(requirement.expression)};"
        for requirement in task.requirements
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def canonicalize_task(source: str) -> str:
    """Parse then format source, removing comments and incidental whitespace."""

    return format_task(parse_task(source))


def _from_neutral_expression(expression: object) -> Expression:
    """Copy a closed Neutral IR expression into this DSL's own AST."""

    # Kept lazy so parsing/evaluation remain usable when the optional authoring
    # bridge's Neutral IR package is not on the import path.
    from neutral_ir import schema as neutral

    if isinstance(expression, neutral.Visit):
        result: Expression = Visit(str(expression.event))
    elif isinstance(expression, neutral.Avoid):
        result = Avoid(str(expression.event))
    elif isinstance(expression, neutral.OrderedVisit):
        result = OrderedVisit(tuple(map(str, expression.events)))
    elif isinstance(expression, neutral.Deadline):
        result = Deadline(
            str(expression.event),
            int(expression.lower),
            int(expression.upper),
        )
    elif isinstance(expression, neutral.MaintainUntil):
        result = MaintainUntil(
            str(expression.forbidden),
            str(expression.goal),
        )
    elif isinstance(expression, neutral.On):
        result = On(
            str(expression.trigger),
            _from_neutral_expression(expression.obligation),
        )
    elif isinstance(expression, neutral.Alternative):
        result = Alternative(
            tuple(
                _from_neutral_expression(item)
                for item in expression.options
            )
        )
    elif isinstance(expression, neutral.AllOf):
        result = AllOf(
            tuple(
                _from_neutral_expression(item)
                for item in expression.requirements
            )
        )
    elif isinstance(expression, neutral.CountAtMost):
        result = CountAtMost(
            str(expression.event),
            int(expression.maximum),
        )
    elif isinstance(expression, neutral.Once):
        result = Once(str(expression.event))
    elif isinstance(expression, neutral.Since):
        result = Since(
            str(expression.condition),
            str(expression.landmark),
        )
    elif isinstance(expression, neutral.Threshold):
        result = Threshold(
            str(expression.resource),
            str(expression.operator),
            int(expression.value),
        )
    elif isinstance(expression, neutral.Priority):
        result = Priority(
            tuple(
                _from_neutral_expression(item)
                for item in expression.options
            )
        )
    else:
        raise TypeError(f"Unsupported Neutral IR node: {type(expression).__name__}")
    _validate_expression(result)
    return result


def encode_task(task: NeutralTaskSpec) -> str:
    """Losslessly author canonical DSL source from a Neutral IR ``TaskSpec``.

    The returned string explicitly contains the task id, every requirement id,
    and every expression field.  The bridge accepts only the Neutral IR's closed
    node vocabulary and introduces no opaque references or executable hooks.
    """

    from neutral_ir.schema import TaskSpec

    if not isinstance(task, TaskSpec):
        raise TypeError("encode_task expects neutral_ir.schema.TaskSpec")
    dsl_task = Task(
        str(task.id),
        tuple(
            Requirement(
                str(requirement.id),
                _from_neutral_expression(requirement.expr),
            )
            for requirement in task.requirements
        ),
    )
    return format_task(dsl_task)


class TraceStep(Protocol):
    propositions: Set[str]

    def resource(self, name: str) -> int: ...


_COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def _has(trace: Sequence[TraceStep], index: int, event: str) -> bool:
    return 0 <= index < len(trace) and event in trace[index].propositions


def evaluate_expression(
    expression: Expression,
    trace: Sequence[TraceStep],
    position: int = 0,
) -> bool:
    """Evaluate an expression on a finite trace suffix starting at ``position``."""

    if position < 0:
        raise ValueError("position must be nonnegative")
    if isinstance(expression, Visit):
        return any(_has(trace, index, expression.event) for index in range(position, len(trace)))
    if isinstance(expression, Avoid):
        return all(not _has(trace, index, expression.event) for index in range(position, len(trace)))
    if isinstance(expression, OrderedVisit):
        cursor = position
        for event in expression.events:
            match = next(
                (index for index in range(cursor, len(trace)) if _has(trace, index, event)),
                None,
            )
            if match is None:
                return False
            cursor = match + 1
        return True
    if isinstance(expression, Deadline):
        return any(
            _has(trace, index, expression.event)
            for index in range(
                position + expression.lower,
                min(position + expression.upper + 1, len(trace)),
            )
        )
    if isinstance(expression, MaintainUntil):
        goal = next(
            (index for index in range(position, len(trace)) if _has(trace, index, expression.goal)),
            None,
        )
        return goal is not None and all(
            not _has(trace, index, expression.forbidden)
            for index in range(position, goal)
        )
    if isinstance(expression, On):
        return all(
            evaluate_expression(expression.obligation, trace, index)  # type: ignore[arg-type]
            for index in range(position, len(trace))
            if _has(trace, index, expression.trigger)
        )
    if isinstance(expression, Alternative):
        return any(evaluate_expression(item, trace, position) for item in expression.options)
    if isinstance(expression, AllOf):
        return all(evaluate_expression(item, trace, position) for item in expression.requirements)
    if isinstance(expression, CountAtMost):
        return sum(
            _has(trace, index, expression.event) for index in range(position, len(trace))
        ) <= expression.maximum
    if isinstance(expression, Once):
        return any(_has(trace, index, expression.event) for index in range(0, position + 1))
    if isinstance(expression, Since):
        landmarks = [
            index
            for index in range(0, position + 1)
            if _has(trace, index, expression.landmark)
        ]
        return bool(landmarks) and all(
            _has(trace, index, expression.condition)
            for index in range(landmarks[-1], position + 1)
        )
    if isinstance(expression, Threshold):
        compare = _COMPARISONS[expression.comparison]
        return all(
            compare(trace[index].resource(expression.resource), expression.value)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Priority):
        return priority_rank(expression, trace, position) is not None
    raise TypeError(f"Unsupported expression node: {type(expression)!r}")


def priority_rank(
    expression: Priority,
    trace: Sequence[TraceStep],
    position: int = 0,
) -> int | None:
    """Return the zero-based rank of the first satisfied priority option."""

    return next(
        (
            rank
            for rank, option in enumerate(expression.options)
            if evaluate_expression(option, trace, position)
        ),
        None,
    )


def requirement_results(
    task: Task, trace: Sequence[TraceStep]
) -> dict[str, bool]:
    """Return deterministic, source-order per-requirement diagnostics."""

    return {
        requirement.id: evaluate_expression(requirement.expression, trace)
        for requirement in task.requirements
    }


def evaluate(task: Task, trace: Sequence[TraceStep]) -> bool:
    """Evaluate a parsed task; all top-level requirements are conjunctive."""

    validate_task(task)
    return all(requirement_results(task, trace).values())


def evaluate_task(source: str, trace: Sequence[TraceStep]) -> bool:
    """Parse and evaluate a task source string on ``trace``."""

    return evaluate(parse_task(source), trace)


__all__ = [
    "DESIGN_SEED",
    "TaskSourceError",
    "Expr",
    "Visit",
    "Avoid",
    "OrderedVisit",
    "Deadline",
    "MaintainUntil",
    "On",
    "Alternative",
    "AllOf",
    "CountAtMost",
    "Once",
    "Since",
    "Threshold",
    "Priority",
    "Requirement",
    "Task",
    "parse_task",
    "format_task",
    "canonicalize_task",
    "encode_task",
    "validate_task",
    "evaluate_expression",
    "priority_rank",
    "requirement_results",
    "evaluate",
    "evaluate_task",
]
