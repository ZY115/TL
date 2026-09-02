"""Parser, canonical formatter, and finite-trace interpreter for RouteTask DSL.

RouteTask is deliberately a closed task language.  Its call names denote
warehouse mission patterns; they are not arbitrary functions and cannot be
extended from task source.
"""

from __future__ import annotations

import json
import operator
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from neutral_ir import schema as neutral_schema


class TaskSyntaxError(ValueError):
    """Raised when RouteTask source is lexically or grammatically invalid."""


class TaskValidationError(ValueError):
    """Raised when a well-formed call has invalid task-domain arguments."""


class Expr:
    """Marker base class for closed RouteTask expression nodes."""


@dataclass(frozen=True, slots=True)
class Reach(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Never(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class Route(Expr):
    events: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReachBetween(Expr):
    event: str
    lower: int
    upper: int


@dataclass(frozen=True, slots=True)
class AvoidUntil(Expr):
    forbidden: str
    goal: str


@dataclass(frozen=True, slots=True)
class AfterEach(Expr):
    trigger: str
    obligation: Expr


@dataclass(frozen=True, slots=True)
class AnyOf(Expr):
    options: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class AllOf(Expr):
    requirements: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class VisitsAtMost(Expr):
    event: str
    maximum: int


@dataclass(frozen=True, slots=True)
class Seen(Expr):
    event: str


@dataclass(frozen=True, slots=True)
class ConditionSince(Expr):
    condition: str
    landmark: str


@dataclass(frozen=True, slots=True)
class MaintainResource(Expr):
    resource: str
    comparison: str
    value: int


@dataclass(frozen=True, slots=True)
class Prefer(Expr):
    options: tuple[Expr, ...]


Expression: TypeAlias = (
    Reach
    | Never
    | Route
    | ReachBetween
    | AvoidUntil
    | AfterEach
    | AnyOf
    | AllOf
    | VisitsAtMost
    | Seen
    | ConditionSince
    | MaintainResource
    | Prefer
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
    value: str | int
    offset: int


_PUNCTUATION = {
    "{": "LBRACE",
    "}": "RBRACE",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
    ":": "COLON",
    ";": "SEMI",
}


def _tokenize(source: str) -> tuple[_Token, ...]:
    """Tokenize the small closed grammar without invoking host-language parsers."""

    tokens: list[_Token] = []
    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(source):
        character = source[cursor]
        if character.isspace():
            cursor += 1
            continue
        if character in _PUNCTUATION:
            tokens.append(_Token(_PUNCTUATION[character], character, cursor))
            cursor += 1
            continue
        if character == '"':
            try:
                value, end = decoder.raw_decode(source, cursor)
            except json.JSONDecodeError as error:
                raise TaskSyntaxError(
                    f"invalid JSON string at offset {cursor}: {error.msg}"
                ) from None
            if not isinstance(value, str):
                raise TaskSyntaxError(f"expected string at offset {cursor}")
            tokens.append(_Token("STRING", value, cursor))
            cursor = end
            continue
        if character == "-" or character.isdigit():
            start = cursor
            if character == "-":
                cursor += 1
                if cursor >= len(source) or not source[cursor].isdigit():
                    raise TaskSyntaxError(f"invalid integer at offset {start}")
            if source[cursor] == "0":
                cursor += 1
            else:
                while cursor < len(source) and source[cursor].isdigit():
                    cursor += 1
            tokens.append(_Token("INTEGER", int(source[start:cursor]), start))
            continue
        if character.isalpha() or character == "_":
            start = cursor
            cursor += 1
            while cursor < len(source) and (
                source[cursor].isalnum() or source[cursor] == "_"
            ):
                cursor += 1
            tokens.append(_Token("NAME", source[start:cursor], start))
            continue
        raise TaskSyntaxError(
            f"unexpected character {character!r} at offset {cursor}"
        )
    tokens.append(_Token("EOF", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, source: str):
        self._tokens = _tokenize(source)
        self._cursor = 0

    @property
    def current(self) -> _Token:
        return self._tokens[self._cursor]

    def accept(self, kind: str, value: str | None = None) -> _Token | None:
        token = self.current
        if token.kind == kind and (value is None or token.value == value):
            self._cursor += 1
            return token
        return None

    def expect(self, kind: str, value: str | None = None) -> _Token:
        token = self.accept(kind, value)
        if token is not None:
            return token
        expected = value if value is not None else kind.lower()
        raise TaskSyntaxError(
            f"expected {expected!r} at offset {self.current.offset}, "
            f"found {self.current.value!r}"
        )

    def parse_task(self) -> Task:
        self.expect("NAME", "task")
        task_id = self.expect("STRING").value
        assert isinstance(task_id, str)
        _validate_label("task id", task_id)
        self.expect("LBRACE")
        requirements: list[Requirement] = []
        while self.current.kind != "RBRACE":
            if self.current.kind == "EOF":
                raise TaskSyntaxError("unterminated task body")
            requirements.append(self.parse_requirement())
        self.expect("RBRACE")
        self.expect("EOF")
        if not requirements:
            raise TaskValidationError("a task must have at least one requirement")
        ids = [item.id for item in requirements]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise TaskValidationError(
                "duplicate requirement id(s): " + ", ".join(duplicates)
            )
        return Task(task_id, tuple(requirements))

    def parse_requirement(self) -> Requirement:
        self.expect("NAME", "require")
        requirement_id = self.expect("STRING").value
        assert isinstance(requirement_id, str)
        _validate_label("requirement id", requirement_id)
        self.expect("COLON")
        expression = self.parse_expression()
        self.expect("SEMI")
        return Requirement(requirement_id, expression)

    def parse_expression(self) -> Expression:
        call = self.expect("NAME").value
        assert isinstance(call, str)
        self.expect("LPAREN")
        arguments: list[str | int | Expression] = []
        if self.current.kind != "RPAREN":
            while True:
                if self.current.kind == "STRING":
                    arguments.append(self.expect("STRING").value)
                elif self.current.kind == "INTEGER":
                    arguments.append(self.expect("INTEGER").value)
                elif self.current.kind == "NAME":
                    arguments.append(self.parse_expression())
                else:
                    raise TaskSyntaxError(
                        f"expected expression argument at offset {self.current.offset}"
                    )
                if self.accept("COMMA") is None:
                    break
        self.expect("RPAREN")
        return _build_expression(call, arguments)


def _validate_label(role: str, value: str) -> str:
    if not value:
        raise TaskValidationError(f"{role} must be a non-empty string")
    return value


def _expect_arity(call: str, arguments: Sequence[object], count: int) -> None:
    if len(arguments) != count:
        raise TaskValidationError(
            f"{call} expects {count} argument(s), received {len(arguments)}"
        )


def _expect_minimum_arity(call: str, arguments: Sequence[object], count: int) -> None:
    if len(arguments) < count:
        raise TaskValidationError(
            f"{call} expects at least {count} argument(s), received {len(arguments)}"
        )


def _string(call: str, argument: object, index: int) -> str:
    if not isinstance(argument, str):
        raise TaskValidationError(f"{call} argument {index} must be a string")
    return _validate_label(f"{call} argument {index}", argument)


def _integer(call: str, argument: object, index: int) -> int:
    # bool is not generated by the grammar, but the explicit check documents the API.
    if isinstance(argument, bool) or not isinstance(argument, int):
        raise TaskValidationError(f"{call} argument {index} must be an integer")
    return argument


def _expression(call: str, argument: object, index: int) -> Expression:
    if not isinstance(argument, Expr):
        raise TaskValidationError(f"{call} argument {index} must be a task expression")
    return argument  # type: ignore[return-value]


def _build_expression(
    call: str, arguments: Sequence[str | int | Expression]
) -> Expression:
    if call == "reach":
        _expect_arity(call, arguments, 1)
        return Reach(_string(call, arguments[0], 1))
    if call == "never":
        _expect_arity(call, arguments, 1)
        return Never(_string(call, arguments[0], 1))
    if call == "route":
        _expect_minimum_arity(call, arguments, 1)
        return Route(tuple(_string(call, item, index + 1) for index, item in enumerate(arguments)))
    if call == "reach_between":
        _expect_arity(call, arguments, 3)
        event = _string(call, arguments[0], 1)
        lower = _integer(call, arguments[1], 2)
        upper = _integer(call, arguments[2], 3)
        if lower < 0 or upper < lower:
            raise TaskValidationError(
                "reach_between requires 0 <= lower <= upper"
            )
        return ReachBetween(event, lower, upper)
    if call == "avoid_until":
        _expect_arity(call, arguments, 2)
        return AvoidUntil(
            _string(call, arguments[0], 1), _string(call, arguments[1], 2)
        )
    if call == "after_each":
        _expect_arity(call, arguments, 2)
        return AfterEach(
            _string(call, arguments[0], 1),
            _expression(call, arguments[1], 2),
        )
    if call in {"any_of", "all_of", "prefer"}:
        _expect_minimum_arity(call, arguments, 2)
        items = tuple(
            _expression(call, item, index + 1)
            for index, item in enumerate(arguments)
        )
        if call == "any_of":
            return AnyOf(items)
        if call == "all_of":
            return AllOf(items)
        return Prefer(items)
    if call == "visits_at_most":
        _expect_arity(call, arguments, 2)
        maximum = _integer(call, arguments[1], 2)
        if maximum < 0:
            raise TaskValidationError("visits_at_most maximum must be non-negative")
        return VisitsAtMost(_string(call, arguments[0], 1), maximum)
    if call == "seen":
        _expect_arity(call, arguments, 1)
        return Seen(_string(call, arguments[0], 1))
    if call == "condition_since":
        _expect_arity(call, arguments, 2)
        return ConditionSince(
            _string(call, arguments[0], 1), _string(call, arguments[1], 2)
        )
    if call == "maintain_resource":
        _expect_arity(call, arguments, 3)
        comparison = _string(call, arguments[1], 2)
        if comparison not in _COMPARISONS:
            raise TaskValidationError(
                "maintain_resource comparison must be one of <, <=, ==, >=, >"
            )
        return MaintainResource(
            _string(call, arguments[0], 1),
            comparison,
            _integer(call, arguments[2], 3),
        )
    raise TaskValidationError(f"unknown RouteTask call: {call}")


def parse_task(source: str) -> Task:
    """Parse and validate one complete RouteTask document."""

    if not isinstance(source, str):
        raise TypeError("task source must be a string")
    return _Parser(source).parse_task()


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def format_expression(expression: Expression) -> str:
    """Return the unique canonical source spelling for an expression."""

    if isinstance(expression, Reach):
        return f"reach({_quote(expression.event)})"
    if isinstance(expression, Never):
        return f"never({_quote(expression.event)})"
    if isinstance(expression, Route):
        return "route(" + ", ".join(map(_quote, expression.events)) + ")"
    if isinstance(expression, ReachBetween):
        return (
            f"reach_between({_quote(expression.event)}, "
            f"{expression.lower}, {expression.upper})"
        )
    if isinstance(expression, AvoidUntil):
        return (
            f"avoid_until({_quote(expression.forbidden)}, "
            f"{_quote(expression.goal)})"
        )
    if isinstance(expression, AfterEach):
        return (
            f"after_each({_quote(expression.trigger)}, "
            f"{format_expression(expression.obligation)})"
        )
    if isinstance(expression, AnyOf):
        return "any_of(" + ", ".join(map(format_expression, expression.options)) + ")"
    if isinstance(expression, AllOf):
        return "all_of(" + ", ".join(
            map(format_expression, expression.requirements)
        ) + ")"
    if isinstance(expression, VisitsAtMost):
        return f"visits_at_most({_quote(expression.event)}, {expression.maximum})"
    if isinstance(expression, Seen):
        return f"seen({_quote(expression.event)})"
    if isinstance(expression, ConditionSince):
        return (
            f"condition_since({_quote(expression.condition)}, "
            f"{_quote(expression.landmark)})"
        )
    if isinstance(expression, MaintainResource):
        return (
            f"maintain_resource({_quote(expression.resource)}, "
            f"{_quote(expression.comparison)}, {expression.value})"
        )
    if isinstance(expression, Prefer):
        return "prefer(" + ", ".join(map(format_expression, expression.options)) + ")"
    raise TypeError(f"unsupported RouteTask node: {type(expression)!r}")


def format_task(task: Task) -> str:
    """Serialize a validated task into deterministic canonical source."""

    if not isinstance(task, Task):
        raise TypeError("format_task expects a Task")
    lines = [f"task {_quote(task.id)} {{"]
    lines.extend(
        f"  require {_quote(requirement.id)}: "
        f"{format_expression(requirement.expression)};"
        for requirement in task.requirements
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def canonicalize(source: str) -> str:
    """Parse, validate, and emit canonical RouteTask source."""

    return format_task(parse_task(source))


def _from_neutral(expression: neutral_schema.Expression) -> Expression:
    """Translate a closed Neutral IR node into its RouteTask AST counterpart."""

    if isinstance(expression, neutral_schema.Visit):
        return Reach(expression.event)
    if isinstance(expression, neutral_schema.Avoid):
        return Never(expression.event)
    if isinstance(expression, neutral_schema.OrderedVisit):
        return Route(expression.events)
    if isinstance(expression, neutral_schema.Deadline):
        return ReachBetween(expression.event, expression.lower, expression.upper)
    if isinstance(expression, neutral_schema.MaintainUntil):
        return AvoidUntil(expression.forbidden, expression.goal)
    if isinstance(expression, neutral_schema.On):
        return AfterEach(expression.trigger, _from_neutral(expression.obligation))
    if isinstance(expression, neutral_schema.Alternative):
        return AnyOf(tuple(_from_neutral(item) for item in expression.options))
    if isinstance(expression, neutral_schema.AllOf):
        return AllOf(tuple(_from_neutral(item) for item in expression.requirements))
    if isinstance(expression, neutral_schema.CountAtMost):
        return VisitsAtMost(expression.event, expression.maximum)
    if isinstance(expression, neutral_schema.Once):
        return Seen(expression.event)
    if isinstance(expression, neutral_schema.Since):
        return ConditionSince(expression.condition, expression.landmark)
    if isinstance(expression, neutral_schema.Threshold):
        return MaintainResource(
            expression.resource, expression.operator, expression.value
        )
    if isinstance(expression, neutral_schema.Priority):
        return Prefer(tuple(_from_neutral(item) for item in expression.options))
    raise TypeError(f"unsupported Neutral IR node: {type(expression)!r}")


def _to_neutral(expression: Expression) -> neutral_schema.Expression:
    """Translate a RouteTask AST node into the corresponding Neutral IR node."""

    if isinstance(expression, Reach):
        return neutral_schema.Visit(expression.event)
    if isinstance(expression, Never):
        return neutral_schema.Avoid(expression.event)
    if isinstance(expression, Route):
        return neutral_schema.OrderedVisit(expression.events)
    if isinstance(expression, ReachBetween):
        return neutral_schema.Deadline(
            expression.event, expression.lower, expression.upper
        )
    if isinstance(expression, AvoidUntil):
        return neutral_schema.MaintainUntil(expression.forbidden, expression.goal)
    if isinstance(expression, AfterEach):
        return neutral_schema.On(
            expression.trigger, _to_neutral(expression.obligation)
        )
    if isinstance(expression, AnyOf):
        return neutral_schema.Alternative(
            tuple(_to_neutral(item) for item in expression.options)
        )
    if isinstance(expression, AllOf):
        return neutral_schema.AllOf(
            tuple(_to_neutral(item) for item in expression.requirements)
        )
    if isinstance(expression, VisitsAtMost):
        return neutral_schema.CountAtMost(expression.event, expression.maximum)
    if isinstance(expression, Seen):
        return neutral_schema.Once(expression.event)
    if isinstance(expression, ConditionSince):
        return neutral_schema.Since(expression.condition, expression.landmark)
    if isinstance(expression, MaintainResource):
        return neutral_schema.Threshold(
            expression.resource, expression.comparison, expression.value
        )
    if isinstance(expression, Prefer):
        return neutral_schema.Priority(
            tuple(_to_neutral(item) for item in expression.options)
        )
    raise TypeError(f"unsupported RouteTask node: {type(expression)!r}")


def encode_task(task: neutral_schema.TaskSpec) -> str:
    """Encode a Neutral IR task as complete, canonical RouteTask source.

    The result is intentionally self-contained: task ID, requirement IDs, node
    choices, nesting, ordered options, bounds, comparisons, and scalar values
    all remain explicit source tokens.
    """

    if not isinstance(task, neutral_schema.TaskSpec):
        raise TypeError("encode_task expects a neutral_ir.schema.TaskSpec")
    route_task = Task(
        task.id,
        tuple(
            Requirement(item.id, _from_neutral(item.expr))
            for item in task.requirements
        ),
    )
    # Reparse to apply exactly the same domain validation as authored source.
    return canonicalize(format_task(route_task))


def decode_task(source: str) -> neutral_schema.TaskSpec:
    """Parse RouteTask source and reconstruct its complete Neutral IR task."""

    task = parse_task(source)
    return neutral_schema.TaskSpec(
        task.id,
        tuple(
            neutral_schema.Requirement(
                requirement.id, _to_neutral(requirement.expression)
            )
            for requirement in task.requirements
        ),
    )


_COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    ">=": operator.ge,
    ">": operator.gt,
}


def _propositions(step: object) -> frozenset[str]:
    if isinstance(step, Mapping):
        if "propositions" not in step:
            raise TypeError("trace mapping step has no 'propositions' field")
        values = step["propositions"]
    elif hasattr(step, "propositions"):
        values = getattr(step, "propositions")
    else:
        raise TypeError("trace step must expose propositions")
    if isinstance(values, str):
        raise TypeError("trace propositions must be a collection, not a string")
    try:
        return frozenset(str(value) for value in values)  # type: ignore[union-attr]
    except TypeError:
        raise TypeError("trace propositions must be iterable") from None


def _has(trace: Sequence[object], index: int, event: str) -> bool:
    return 0 <= index < len(trace) and event in _propositions(trace[index])


def _resource(step: object, name: str) -> int:
    method = getattr(step, "resource", None)
    if callable(method):
        value = method(name)
    elif isinstance(step, Mapping):
        resources = step.get("resources")
        if not isinstance(resources, Mapping) or name not in resources:
            raise KeyError(f"unknown resource: {name}")
        value = resources[name]
    else:
        resources = getattr(step, "resources", None)
        try:
            value = dict(resources)[name]
        except (TypeError, ValueError, KeyError):
            raise KeyError(f"unknown resource: {name}") from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"resource {name!r} must have an integer value")
    return value


def evaluate_expression(
    expression: Expression, trace: Sequence[object], position: int = 0
) -> bool:
    """Evaluate an expression using direct finite-trace mission semantics."""

    if not 0 <= position <= len(trace):
        raise IndexError("evaluation position is outside the finite trace")
    if isinstance(expression, Reach):
        return any(
            _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Never):
        return all(
            not _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Route):
        cursor = position
        for event in expression.events:
            match = next(
                (
                    index
                    for index in range(cursor, len(trace))
                    if _has(trace, index, event)
                ),
                None,
            )
            if match is None:
                return False
            cursor = match + 1
        return True
    if isinstance(expression, ReachBetween):
        return any(
            _has(trace, index, expression.event)
            for index in range(
                position + expression.lower,
                min(position + expression.upper + 1, len(trace)),
            )
        )
    if isinstance(expression, AvoidUntil):
        goal_index = next(
            (
                index
                for index in range(position, len(trace))
                if _has(trace, index, expression.goal)
            ),
            None,
        )
        return goal_index is not None and all(
            not _has(trace, index, expression.forbidden)
            for index in range(position, goal_index)
        )
    if isinstance(expression, AfterEach):
        return all(
            evaluate_expression(expression.obligation, trace, index)
            for index in range(position, len(trace))
            if _has(trace, index, expression.trigger)
        )
    if isinstance(expression, AnyOf):
        return any(
            evaluate_expression(option, trace, position)
            for option in expression.options
        )
    if isinstance(expression, AllOf):
        return all(
            evaluate_expression(requirement, trace, position)
            for requirement in expression.requirements
        )
    if isinstance(expression, VisitsAtMost):
        visits = sum(
            _has(trace, index, expression.event)
            for index in range(position, len(trace))
        )
        return visits <= expression.maximum
    if isinstance(expression, Seen):
        return any(
            _has(trace, index, expression.event)
            for index in range(0, position + 1)
        )
    if isinstance(expression, ConditionSince):
        landmarks = [
            index
            for index in range(0, position + 1)
            if _has(trace, index, expression.landmark)
        ]
        return bool(landmarks) and all(
            _has(trace, index, expression.condition)
            for index in range(landmarks[-1], position + 1)
        )
    if isinstance(expression, MaintainResource):
        compare = _COMPARISONS[expression.comparison]
        return all(
            compare(_resource(trace[index], expression.resource), expression.value)
            for index in range(position, len(trace))
        )
    if isinstance(expression, Prefer):
        # Preference affects ranking, while Boolean task acceptance asks whether
        # at least one ranked option succeeds.
        return any(
            evaluate_expression(option, trace, position)
            for option in expression.options
        )
    raise TypeError(f"unsupported RouteTask node: {type(expression)!r}")


def preference_rank(
    expression: Prefer, trace: Sequence[object], position: int = 0
) -> int | None:
    """Return the zero-based rank of the first successful preferred option."""

    return next(
        (
            index
            for index, option in enumerate(expression.options)
            if evaluate_expression(option, trace, position)
        ),
        None,
    )


def requirement_diagnostics(
    task: Task, trace: Sequence[object]
) -> dict[str, bool]:
    """Evaluate each top-level requirement without changing task acceptance."""

    return {
        requirement.id: evaluate_expression(requirement.expression, trace)
        for requirement in task.requirements
    }


def evaluate_task(source: str, trace: Sequence[object]) -> bool:
    """Parse ``source`` and accept iff every named requirement is satisfied."""

    return all(requirement_diagnostics(parse_task(source), trace).values())
