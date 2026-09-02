"""Warehouse DSL: parser, canonical formatter, and finite-trace interpreter.

This module implements a small closed language for authoring warehouse
operating requirements (pickup, inspection, delivery, charging, hazard
avoidance) over finite traces, per the trace contract in ``warehouse.md``.

The language has exactly eight constructs, described fully in ``README.md``:

    visit(target)
    avoid(target)
    order(target, target, ...)
    within(target, lo, hi[, then=requirement])
    avoid_until(avoid_target, reach_target)
    every(trigger_target, requirement)
    and(requirement, requirement, ...)
    or(requirement, requirement, ...)

A ``target`` is a single label or an ``any(label, label, ...)`` disjunction
of labels. There is no ``eval``, no ``exec``, no import of any kind from
task source, no arbitrary Python callback, and no serialization of an
external formula language: the grammar below is the complete surface of
the language, and anything outside it is rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence, Tuple, Union

__all__ = [
    "WarehouseDSLError",
    "WarehouseSyntaxError",
    "WarehouseValidationError",
    "Label",
    "AnyOf",
    "Visit",
    "Avoid",
    "Order",
    "Within",
    "AvoidUntil",
    "Every",
    "And",
    "Or",
    "parse_task",
    "canonicalize",
    "evaluate_task",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WarehouseDSLError(ValueError):
    """Base class for every error this package raises.

    Always a ``ValueError`` subclass, per the required API contract.
    """


class WarehouseSyntaxError(WarehouseDSLError):
    """The source text could not be tokenized or does not match the grammar.

    Covers unrecognized characters, unknown top-level constructs, wrong or
    missing punctuation, and trailing text after a complete requirement.
    """


class WarehouseValidationError(WarehouseDSLError):
    """The source matched the grammar but violates a static well-formedness
    rule (for example ``within`` bounds with ``lo > hi``, an ``order``/
    ``and``/``or``/``any`` group with too few members, or a reserved word
    used as a label).
    """


# ---------------------------------------------------------------------------
# Immutable AST
#
# Every node is a frozen (hence immutable and hashable) dataclass. Tuples,
# never lists, hold ordered children, so a fully parsed task is a genuinely
# immutable tree: no attribute can be reassigned and no child container can
# be mutated in place.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Label:
    """A single proposition label, e.g. the pickup shelf ``A``."""

    name: str


@dataclass(frozen=True)
class AnyOf:
    """A disjunction of two or more labels: matches a step containing any
    one of them."""

    labels: Tuple[str, ...]


Target = Union[Label, AnyOf]


@dataclass(frozen=True)
class Visit:
    """``visit(target)`` -- reach target at or after the current start."""

    target: Target


@dataclass(frozen=True)
class Avoid:
    """``avoid(target)`` -- target never holds at or after the current
    start."""

    target: Target


@dataclass(frozen=True)
class Order:
    """``order(t1, t2, ..., tn)`` -- strictly increasing visits to each
    target in turn, n >= 2."""

    targets: Tuple[Target, ...]


@dataclass(frozen=True)
class Within:
    """``within(target, lo, hi[, then=requirement])`` -- a bounded reach,
    optionally carrying a follow-on requirement evaluated from the chosen
    step."""

    target: Target
    lo: int
    hi: int
    then: Optional["Requirement"] = None


@dataclass(frozen=True)
class AvoidUntil:
    """``avoid_until(avoid_target, reach_target)`` -- reach_target must
    occur at or after the current start, and avoid_target must not occur
    strictly before the first such occurrence."""

    avoid_target: Target
    reach_target: Target


@dataclass(frozen=True)
class Every:
    """``every(trigger, body)`` -- body must hold, started fresh at each
    step where trigger holds; vacuously true if trigger never holds."""

    trigger: Target
    body: "Requirement"


@dataclass(frozen=True)
class And:
    """``and(r1, r2, ..., rn)`` -- conjunction, n >= 2, all evaluated from
    the same start."""

    children: Tuple["Requirement", ...]


@dataclass(frozen=True)
class Or:
    """``or(r1, r2, ..., rn)`` -- disjunction, n >= 2, all evaluated from
    the same start."""

    children: Tuple["Requirement", ...]


Requirement = Union[Visit, Avoid, Order, Within, AvoidUntil, Every, And, Or]


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_TOKEN_SPEC: Tuple[Tuple[str, str], ...] = (
    ("WS", r"[ \t\r\n]+"),
    ("COMMENT", r"\#[^\n]*"),
    ("INT", r"\d+"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("EQUALS", r"="),
)
_TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC)
)


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    pos: int


def _tokenize(source: str) -> List[_Token]:
    tokens: List[_Token] = []
    pos = 0
    length = len(source)
    while pos < length:
        match = _TOKEN_RE.match(source, pos)
        if match is None:
            raise WarehouseSyntaxError(
                f"unrecognized character {source[pos]!r} at position {pos}"
            )
        kind = match.lastgroup
        text = match.group()
        if kind not in ("WS", "COMMENT"):
            tokens.append(_Token(kind, text, pos))
        pos = match.end()
    tokens.append(_Token("EOF", "", length))
    return tokens


# ---------------------------------------------------------------------------
# Grammar keywords
# ---------------------------------------------------------------------------

_CONSTRUCT_KEYWORDS = frozenset(
    {"visit", "avoid", "order", "within", "avoid_until", "every", "and", "or"}
)
# Words that may not be used as an author-chosen label, because the grammar
# gives them a fixed structural meaning somewhere in the language.
_RESERVED_WORDS = _CONSTRUCT_KEYWORDS | {"then", "any"}


# ---------------------------------------------------------------------------
# Parser (recursive descent, one token of lookahead)
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: Sequence[_Token]):
        self._tokens = tokens
        self._i = 0

    def _peek(self) -> _Token:
        return self._tokens[self._i]

    def _advance(self) -> _Token:
        token = self._tokens[self._i]
        self._i += 1
        return token

    def _expect(self, kind: str) -> _Token:
        token = self._peek()
        if token.kind != kind:
            found = token.text if token.kind != "EOF" else "<end of source>"
            raise WarehouseSyntaxError(
                f"expected {kind} but found {token.kind} {found!r} "
                f"at position {token.pos}"
            )
        return self._advance()

    def _expect_keyword(self, text: str) -> _Token:
        token = self._peek()
        if token.kind != "IDENT" or token.text != text:
            found = token.text if token.kind != "EOF" else "<end of source>"
            raise WarehouseSyntaxError(
                f"expected keyword {text!r} but found {found!r} "
                f"at position {token.pos}"
            )
        return self._advance()

    # -- top level ----------------------------------------------------

    def parse_task(self) -> Requirement:
        requirement = self.parse_requirement()
        self._expect("EOF")
        return requirement

    # -- requirement ----------------------------------------------------

    def parse_requirement(self) -> Requirement:
        token = self._expect("IDENT")
        keyword = token.text
        if keyword not in _CONSTRUCT_KEYWORDS:
            raise WarehouseSyntaxError(
                f"unknown construct {keyword!r} at position {token.pos}"
            )
        self._expect("LPAREN")

        if keyword == "visit":
            target = self.parse_target()
            self._expect("RPAREN")
            return Visit(target)

        if keyword == "avoid":
            target = self.parse_target()
            self._expect("RPAREN")
            return Avoid(target)

        if keyword == "order":
            targets = [self.parse_target()]
            while self._peek().kind == "COMMA":
                self._advance()
                targets.append(self.parse_target())
            self._expect("RPAREN")
            if len(targets) < 2:
                raise WarehouseValidationError(
                    "order(...) requires at least 2 targets"
                )
            return Order(tuple(targets))

        if keyword == "within":
            target = self.parse_target()
            self._expect("COMMA")
            lo_token = self._expect("INT")
            lo = int(lo_token.text)
            self._expect("COMMA")
            hi_token = self._expect("INT")
            hi = int(hi_token.text)
            then: Optional[Requirement] = None
            if self._peek().kind == "COMMA":
                self._advance()
                self._expect_keyword("then")
                self._expect("EQUALS")
                then = self.parse_requirement()
            self._expect("RPAREN")
            if lo > hi:
                raise WarehouseValidationError(
                    f"within(...) lower bound {lo} exceeds upper bound {hi} "
                    f"(at position {token.pos})"
                )
            return Within(target, lo, hi, then)

        if keyword == "avoid_until":
            avoid_target = self.parse_target()
            self._expect("COMMA")
            reach_target = self.parse_target()
            self._expect("RPAREN")
            return AvoidUntil(avoid_target, reach_target)

        if keyword == "every":
            trigger = self.parse_target()
            self._expect("COMMA")
            body = self.parse_requirement()
            self._expect("RPAREN")
            return Every(trigger, body)

        if keyword in ("and", "or"):
            children = [self.parse_requirement()]
            while self._peek().kind == "COMMA":
                self._advance()
                children.append(self.parse_requirement())
            self._expect("RPAREN")
            if len(children) < 2:
                raise WarehouseValidationError(
                    f"{keyword}(...) requires at least 2 sub-requirements"
                )
            if keyword == "and":
                return And(tuple(children))
            return Or(tuple(children))

        raise AssertionError("unreachable: unhandled construct keyword")

    # -- target ----------------------------------------------------

    def parse_target(self) -> Target:
        token = self._peek()
        if token.kind == "IDENT" and token.text == "any":
            self._advance()
            self._expect("LPAREN")
            labels = [self.parse_label()]
            while self._peek().kind == "COMMA":
                self._advance()
                labels.append(self.parse_label())
            self._expect("RPAREN")
            if len(labels) < 2:
                raise WarehouseValidationError(
                    "any(...) requires at least 2 labels"
                )
            return AnyOf(tuple(labels))
        return Label(self.parse_label())

    def parse_label(self) -> str:
        token = self._expect("IDENT")
        if token.text in _RESERVED_WORDS:
            raise WarehouseValidationError(
                f"reserved word {token.text!r} cannot be used as a label "
                f"(position {token.pos})"
            )
        return token.text


def parse_task(source: str) -> Requirement:
    """Parse ``source`` into an immutable requirement tree.

    Raises a :class:`WarehouseDSLError` (a ``ValueError`` subclass) if
    ``source`` is not a string, cannot be tokenized, does not match the
    grammar, uses an unknown construct, or violates a static
    well-formedness rule.
    """

    if not isinstance(source, str):
        raise WarehouseSyntaxError("source must be a string")
    tokens = _tokenize(source)
    parser = _Parser(tokens)
    return parser.parse_task()


# ---------------------------------------------------------------------------
# Canonical formatter
# ---------------------------------------------------------------------------


def _format_target(target: Target) -> str:
    if isinstance(target, Label):
        return target.name
    if isinstance(target, AnyOf):
        return "any(" + ", ".join(target.labels) + ")"
    raise TypeError(f"not a target node: {target!r}")


def _format(node: Requirement) -> str:
    if isinstance(node, Visit):
        return f"visit({_format_target(node.target)})"
    if isinstance(node, Avoid):
        return f"avoid({_format_target(node.target)})"
    if isinstance(node, Order):
        return "order(" + ", ".join(_format_target(t) for t in node.targets) + ")"
    if isinstance(node, Within):
        rendered = (
            f"within({_format_target(node.target)}, {node.lo}, {node.hi}"
        )
        if node.then is not None:
            rendered += f", then={_format(node.then)}"
        return rendered + ")"
    if isinstance(node, AvoidUntil):
        return (
            "avoid_until("
            f"{_format_target(node.avoid_target)}, "
            f"{_format_target(node.reach_target)})"
        )
    if isinstance(node, Every):
        return f"every({_format_target(node.trigger)}, {_format(node.body)})"
    if isinstance(node, And):
        return "and(" + ", ".join(_format(c) for c in node.children) + ")"
    if isinstance(node, Or):
        return "or(" + ", ".join(_format(c) for c in node.children) + ")"
    raise TypeError(f"not a requirement node: {node!r}")


def canonicalize(source: str) -> str:
    """Return a canonical, deterministic re-rendering of ``source``.

    ``canonicalize`` parses ``source`` and pretty-prints the resulting
    tree in one fixed style (single line, no comments, minimal integer
    literals, one space after each comma). Formatting is a pure function
    of the parsed tree, and parsing that fixed style reproduces the same
    tree, so ``canonicalize`` is idempotent:
    ``canonicalize(canonicalize(s)) == canonicalize(s)``.

    Raises the same errors as :func:`parse_task` on malformed source.
    """

    tree = parse_task(source)
    return _format(tree)


# ---------------------------------------------------------------------------
# Interpreter
#
# Every construct is evaluated against a finite trace and a start index.
# The start index is the point at which "at or after" and "strictly
# before"/"strictly after" are measured; it is 0 at the top level, the
# index of the matching step inside `every`, and the index of the chosen
# step inside a `within(...).then`. `every` itself always scans the whole
# trace for its trigger, independent of any inherited start, because
# "After A, ..." (warehouse.md) applies to every occurrence of A in the
# run, not to some enclosing sub-window.
# ---------------------------------------------------------------------------


Step = FrozenSet[str]
Trace = Sequence[Step]


def _matches(target: Target, step: Step) -> bool:
    if isinstance(target, Label):
        return target.name in step
    if isinstance(target, AnyOf):
        return any(label in step for label in target.labels)
    raise TypeError(f"not a target node: {target!r}")


def _eval(node: Requirement, trace: Trace, start: int) -> bool:
    n = len(trace)

    if isinstance(node, Visit):
        return any(_matches(node.target, trace[j]) for j in range(start, n))

    if isinstance(node, Avoid):
        return all(not _matches(node.target, trace[j]) for j in range(start, n))

    if isinstance(node, Order):
        cursor = start
        for target in node.targets:
            found: Optional[int] = None
            for j in range(cursor, n):
                if _matches(target, trace[j]):
                    found = j
                    break
            if found is None:
                return False
            cursor = found + 1  # the next target must be strictly later
        return True

    if isinstance(node, Within):
        lo_idx = start + node.lo
        hi_idx = start + node.hi
        window_start = max(lo_idx, 0)
        window_stop = min(hi_idx, n - 1)
        for j in range(window_start, window_stop + 1):
            if _matches(node.target, trace[j]):
                if node.then is None or _eval(node.then, trace, j):
                    return True
        return False

    if isinstance(node, AvoidUntil):
        first_reach: Optional[int] = None
        for j in range(start, n):
            if _matches(node.reach_target, trace[j]):
                first_reach = j
                break
        if first_reach is None:
            return False
        return all(
            not _matches(node.avoid_target, trace[k])
            for k in range(start, first_reach)
        )

    if isinstance(node, Every):
        triggers = [i for i in range(n) if _matches(node.trigger, trace[i])]
        if not triggers:
            return True
        return all(_eval(node.body, trace, i) for i in triggers)

    if isinstance(node, And):
        return all(_eval(child, trace, start) for child in node.children)

    if isinstance(node, Or):
        return any(_eval(child, trace, start) for child in node.children)

    raise TypeError(f"not a requirement node: {node!r}")


def evaluate_task(source: str, trace: Tuple[FrozenSet[str], ...]) -> bool:
    """Parse ``source`` and evaluate it against ``trace``.

    ``trace`` is a finite ordered sequence of steps; each step is the set
    of proposition labels true at that step, per ``warehouse.md``. Always
    returns a ``bool`` -- a finite trace that has not yet satisfied some
    still-pending visit, order, deadline, or until-goal evaluates to
    ``False`` rather than raising.

    Raises the same errors as :func:`parse_task` if ``source`` is
    malformed.
    """

    tree = parse_task(source)
    return _eval(tree, trace, 0)
