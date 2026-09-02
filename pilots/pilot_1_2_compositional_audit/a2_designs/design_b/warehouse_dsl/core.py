"""Core implementation of the Warehouse DSL: tokenizer, parser, immutable AST,
canonical printer, and a finite-trace interpreter.

Design seed tag: 22202  (see README.md)

This module intentionally contains no ``eval``/``exec``, no dynamic import of
task source, no arbitrary Python callback hook, and no general escape hatch.
Every accepted program is one of a small, closed set of warehouse operating
constructs (visit / never / order / avoid_until / whenever / within / then /
all_of / either); anything else is rejected by the parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Union


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WarehouseDSLError(ValueError):
    """Base class for all Warehouse DSL errors. Subclass of ValueError."""


class WarehouseDSLSyntaxError(WarehouseDSLError):
    """Raised when the source text is not a well-formed token tree
    (unbalanced parentheses, stray characters, missing tokens, trailing
    input, wrong token kind in a position)."""


class WarehouseDSLValidationError(WarehouseDSLError):
    """Raised when the token tree is well-formed but violates a grammar or
    semantic rule: an unknown construct, wrong arity, a reserved word used
    as a label, or an out-of-order bound (upper < lower)."""


# ---------------------------------------------------------------------------
# Immutable AST
# ---------------------------------------------------------------------------
#
# Every node is a frozen (hence hashable, immutable) dataclass. Two tiers of
# node exist:
#
#   RequirementNode  -- the top level of a task, and the arguments of
#                        `all_of` / top-level `either`.
#   ScopedNode       -- the body of `whenever`, the body of `then`, and the
#                        arguments of a scoped `either`. A ScopedNode is
#                        always evaluated relative to a "scope start" index
#                        (the step at which its enclosing trigger occurred).
#
# `Visit`, `AvoidUntil`, and `Either` are valid in both tiers because their
# evaluation rule is identical in both places (only the scope-start index
# they receive differs); the parser still only builds each occurrence where
# the grammar in README.md permits it.


@dataclass(frozen=True)
class Visit:
    """``(visit L1 L2 ...)`` -- at least one listed label occurs at or after
    the current scope start."""

    labels: Tuple[str, ...]


@dataclass(frozen=True)
class Never:
    """``(never L)`` -- label L occurs at no step of the whole trace."""

    label: str


@dataclass(frozen=True)
class Order:
    """``(order L1 L2 ... Ln)`` -- there exist strictly increasing indices
    i1 < i2 < ... < in (searched from the current scope start) with L_k at
    step i_k."""

    labels: Tuple[str, ...]


@dataclass(frozen=True)
class AvoidUntil:
    """``(avoid_until X C)`` -- some step at or after the scope start carries
    C, and X does not occur at any step from the scope start up to
    (excluding) the earliest such C."""

    x: str
    c: str


@dataclass(frozen=True)
class Within:
    """``(within LO HI L)`` or ``(within LO HI L (then SCOPED))`` -- some
    step j with (scope start + LO) <= j <= (scope start + HI) carries L;
    if a `then` clause is present, its body must also hold with its own
    scope start set to that chosen j."""

    lo: int
    hi: int
    label: str
    then: Optional["ScopedNode"] = None


@dataclass(frozen=True)
class Whenever:
    """``(whenever T BODY)`` -- for every step of the whole trace that
    carries trigger label T, BODY must hold with its scope start set to
    that step's index. Vacuously true if T never occurs."""

    trigger: str
    body: "ScopedNode"


@dataclass(frozen=True)
class AllOf:
    """``(all_of R1 R2 ...)`` -- every listed requirement holds."""

    children: Tuple["RequirementNode", ...]


@dataclass(frozen=True)
class Either:
    """``(either N1 N2 ...)`` -- at least one listed node holds. Valid as a
    top-level requirement combinator and as a scoped combinator; in both
    cases every child receives the same scope start as the Either node
    itself."""

    children: Tuple["Node", ...]


ScopedNode = Union[Visit, AvoidUntil, Within, Either]
RequirementNode = Union[Visit, Never, Order, AvoidUntil, Whenever, AllOf, Either]
Node = Union[RequirementNode, ScopedNode]

Trace = Sequence[frozenset]


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_KEYWORDS = {
    "visit",
    "never",
    "order",
    "avoid_until",
    "whenever",
    "within",
    "then",
    "all_of",
    "either",
}

_REQUIREMENT_ONLY_KEYWORDS = {"never", "order", "whenever", "all_of"}
_SCOPED_ONLY_KEYWORDS = {"within", "then"}


class _Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: str, pos: int) -> None:
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"_Token({self.kind!r}, {self.value!r}, {self.pos})"


def _tokenize(source: str) -> list:
    tokens = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "#":
            j = source.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        if ch == "(":
            tokens.append(_Token("lparen", "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(_Token("rparen", ")", i))
            i += 1
            continue
        if ch.isalpha():
            j = i + 1
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            tokens.append(_Token("ident", source[i:j], i))
            i = j
            continue
        if ch.isdigit():
            j = i + 1
            while j < n and source[j].isdigit():
                j += 1
            tokens.append(_Token("int", source[i:j], i))
            i = j
            continue
        raise WarehouseDSLSyntaxError(f"unexpected character {ch!r} at position {i}")
    tokens.append(_Token("eof", "", n))
    return tokens


# ---------------------------------------------------------------------------
# Parser (recursive descent over the token list)
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list) -> None:
        self._tokens = tokens
        self._i = 0

    def _peek(self) -> _Token:
        return self._tokens[self._i]

    def _peek2(self) -> _Token:
        j = self._i + 1
        if j < len(self._tokens):
            return self._tokens[j]
        return self._tokens[-1]

    def _advance(self) -> _Token:
        tok = self._tokens[self._i]
        if tok.kind != "eof":
            self._i += 1
        return tok

    def _expect_lparen(self) -> None:
        tok = self._advance()
        if tok.kind != "lparen":
            raise WarehouseDSLSyntaxError(
                f"expected '(' at position {tok.pos}, found {tok.value or '<end of input>'!r}"
            )

    def _expect_rparen(self) -> None:
        tok = self._advance()
        if tok.kind != "rparen":
            raise WarehouseDSLSyntaxError(
                f"expected ')' at position {tok.pos}, found {tok.value or '<end of input>'!r}"
            )

    def _expect_ident(self) -> str:
        tok = self._advance()
        if tok.kind != "ident":
            raise WarehouseDSLSyntaxError(
                f"expected a keyword or label at position {tok.pos}, found {tok.value or '<end of input>'!r}"
            )
        return tok.value

    def _expect_int(self) -> int:
        tok = self._advance()
        if tok.kind != "int":
            raise WarehouseDSLSyntaxError(
                f"expected a nonnegative integer at position {tok.pos}, found {tok.value or '<end of input>'!r}"
            )
        return int(tok.value)

    def _at_rparen(self) -> bool:
        return self._peek().kind == "rparen"

    def _at_then(self) -> bool:
        return (
            self._peek().kind == "lparen"
            and self._peek2().kind == "ident"
            and self._peek2().value == "then"
        )

    def _parse_label(self) -> str:
        tok = self._advance()
        if tok.kind != "ident":
            raise WarehouseDSLSyntaxError(
                f"expected a label at position {tok.pos}, found {tok.value or '<end of input>'!r}"
            )
        if tok.value in _KEYWORDS:
            raise WarehouseDSLValidationError(
                f"'{tok.value}' is a reserved word and cannot be used as a label (position {tok.pos})"
            )
        return tok.value

    def _parse_labels_min(self, minimum: int, construct: str) -> Tuple[str, ...]:
        labels = []
        while not self._at_rparen():
            labels.append(self._parse_label())
        if len(labels) < minimum:
            raise WarehouseDSLValidationError(
                f"'{construct}' requires at least {minimum} label(s), got {len(labels)}"
            )
        return tuple(labels)

    def _parse_requirement_children_min(self, minimum: int, construct: str) -> Tuple[RequirementNode, ...]:
        children = []
        while not self._at_rparen():
            children.append(self.parse_requirement())
        if len(children) < minimum:
            raise WarehouseDSLValidationError(
                f"'{construct}' requires at least {minimum} sub-requirement(s), got {len(children)}"
            )
        return tuple(children)

    def _parse_scoped_children_min(self, minimum: int, construct: str) -> Tuple["ScopedNode", ...]:
        children = []
        while not self._at_rparen():
            children.append(self.parse_scoped())
        if len(children) < minimum:
            raise WarehouseDSLValidationError(
                f"'{construct}' requires at least {minimum} sub-clause(s), got {len(children)}"
            )
        return tuple(children)

    # -- top tier: Requirement ------------------------------------------------

    def parse_requirement(self) -> RequirementNode:
        self._expect_lparen()
        head_tok = self._peek()
        head = self._expect_ident()

        if head == "visit":
            labels = self._parse_labels_min(1, "visit")
            self._expect_rparen()
            return Visit(labels)

        if head == "never":
            label = self._parse_label()
            self._expect_rparen()
            return Never(label)

        if head == "order":
            labels = self._parse_labels_min(2, "order")
            self._expect_rparen()
            return Order(labels)

        if head == "avoid_until":
            x = self._parse_label()
            c = self._parse_label()
            self._expect_rparen()
            return AvoidUntil(x, c)

        if head == "whenever":
            trigger = self._parse_label()
            body = self.parse_scoped()
            self._expect_rparen()
            return Whenever(trigger, body)

        if head == "all_of":
            children = self._parse_requirement_children_min(2, "all_of")
            self._expect_rparen()
            return AllOf(children)

        if head == "either":
            children = self._parse_requirement_children_min(2, "either")
            self._expect_rparen()
            return Either(children)

        if head in _SCOPED_ONLY_KEYWORDS:
            raise WarehouseDSLValidationError(
                f"'{head}' may only appear inside 'whenever' or 'then' (position {head_tok.pos})"
            )
        raise WarehouseDSLValidationError(f"unknown construct '{head}' at position {head_tok.pos}")

    # -- inner tier: ScopedNode (body of whenever / then) ---------------------

    def parse_scoped(self) -> "ScopedNode":
        self._expect_lparen()
        head_tok = self._peek()
        head = self._expect_ident()

        if head == "visit":
            labels = self._parse_labels_min(1, "visit")
            self._expect_rparen()
            return Visit(labels)

        if head == "avoid_until":
            x = self._parse_label()
            c = self._parse_label()
            self._expect_rparen()
            return AvoidUntil(x, c)

        if head == "within":
            lo = self._expect_int()
            hi = self._expect_int()
            label = self._parse_label()
            then_body = None
            if self._at_then():
                self._expect_lparen()
                self._expect_ident()  # consumes 'then'
                then_body = self.parse_scoped()
                self._expect_rparen()
            self._expect_rparen()
            if hi < lo:
                raise WarehouseDSLValidationError(
                    f"'within' upper bound {hi} is less than lower bound {lo}"
                )
            return Within(lo, hi, label, then_body)

        if head == "either":
            children = self._parse_scoped_children_min(2, "either")
            self._expect_rparen()
            return Either(children)

        if head in _REQUIREMENT_ONLY_KEYWORDS:
            raise WarehouseDSLValidationError(
                f"'{head}' cannot appear inside 'whenever' or 'then' (position {head_tok.pos})"
            )
        raise WarehouseDSLValidationError(f"unknown construct '{head}' at position {head_tok.pos}")


# ---------------------------------------------------------------------------
# Public API: parse_task / canonicalize / evaluate_task
# ---------------------------------------------------------------------------


def parse_task(source: str) -> RequirementNode:
    """Parse ``source`` into an immutable requirement tree.

    Raises a :class:`WarehouseDSLError` (a ``ValueError`` subclass) if the
    source is not a well-formed, fully-recognized program.
    """

    if not isinstance(source, str):
        raise WarehouseDSLSyntaxError("source must be a string")

    tokens = _tokenize(source)
    if tokens[0].kind == "eof":
        raise WarehouseDSLSyntaxError("empty source")

    parser = _Parser(tokens)
    node = parser.parse_requirement()

    trailing = parser._peek()
    if trailing.kind != "eof":
        raise WarehouseDSLSyntaxError(
            f"unexpected trailing input at position {trailing.pos}: {trailing.value!r}"
        )
    return node


def _format(node: Node) -> str:
    if isinstance(node, Visit):
        return "(visit " + " ".join(node.labels) + ")"
    if isinstance(node, Never):
        return f"(never {node.label})"
    if isinstance(node, Order):
        return "(order " + " ".join(node.labels) + ")"
    if isinstance(node, AvoidUntil):
        return f"(avoid_until {node.x} {node.c})"
    if isinstance(node, Whenever):
        return f"(whenever {node.trigger} {_format(node.body)})"
    if isinstance(node, AllOf):
        return "(all_of " + " ".join(_format(c) for c in node.children) + ")"
    if isinstance(node, Either):
        return "(either " + " ".join(_format(c) for c in node.children) + ")"
    if isinstance(node, Within):
        if node.then is None:
            return f"(within {node.lo} {node.hi} {node.label})"
        return f"(within {node.lo} {node.hi} {node.label} (then {_format(node.then)}))"
    raise TypeError(f"cannot format node of type {type(node)!r}")  # pragma: no cover


def canonicalize(source: str) -> str:
    """Parse ``source`` and re-render it in a single deterministic form.

    ``canonicalize`` is deterministic (same input always yields the same
    output) and idempotent (``canonicalize(canonicalize(s)) ==
    canonicalize(s)``) because the canonical form is valid input that
    re-parses to an equal tree, and every node type has exactly one
    canonical rendering.
    """

    return _format(parse_task(source))


def _eval(node: Node, trace: Trace, start: int) -> bool:
    if isinstance(node, Visit):
        for i in range(start, len(trace)):
            step = trace[i]
            for label in node.labels:
                if label in step:
                    return True
        return False

    if isinstance(node, Never):
        for step in trace:
            if node.label in step:
                return False
        return True

    if isinstance(node, Order):
        pos = start - 1
        for label in node.labels:
            found = None
            for i in range(pos + 1, len(trace)):
                if label in trace[i]:
                    found = i
                    break
            if found is None:
                return False
            pos = found
        return True

    if isinstance(node, AvoidUntil):
        c_index = None
        for i in range(start, len(trace)):
            if node.c in trace[i]:
                c_index = i
                break
        if c_index is None:
            return False
        for i in range(start, c_index):
            if node.x in trace[i]:
                return False
        return True

    if isinstance(node, Within):
        lo_idx = start + node.lo
        hi_idx = start + node.hi
        for j in range(lo_idx, hi_idx + 1):
            if j >= len(trace):
                break
            if node.label in trace[j]:
                if node.then is None:
                    return True
                if _eval(node.then, trace, j):
                    return True
        return False

    if isinstance(node, Whenever):
        for i in range(len(trace)):
            if node.trigger in trace[i]:
                if not _eval(node.body, trace, i):
                    return False
        return True

    if isinstance(node, AllOf):
        return all(_eval(child, trace, start) for child in node.children)

    if isinstance(node, Either):
        return any(_eval(child, trace, start) for child in node.children)

    raise TypeError(f"unknown node type: {type(node)!r}")  # pragma: no cover


def evaluate_task(source: str, trace: Tuple[frozenset, ...]) -> bool:
    """Parse ``source`` and evaluate it against ``trace``.

    ``trace`` is a finite ordered sequence of steps; each step is a
    ``frozenset`` of the proposition labels true at that step (see
    README.md / warehouse.md). Always returns a ``bool``; an unfinished
    trace that leaves a visit, order, deadline, or until-goal unfulfilled
    evaluates to ``False`` rather than raising.
    """

    node = parse_task(source)
    return bool(_eval(node, trace, 0))
