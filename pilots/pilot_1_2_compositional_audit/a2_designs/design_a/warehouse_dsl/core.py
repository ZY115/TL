"""Warehouse DSL: a closed, compositional language for authoring warehouse
trace requirements (pickup / inspection / delivery / charging / hazard
avoidance), and a reusable interpreter for it.

This module is intentionally self-contained (Python standard library only):
no ``eval``/``exec``, no dynamic imports from task source, and no escape
hatch. Every surface construct is a fixed keyword with a fixed arity; any
other token sequence is rejected by the parser.

Public API (re-exported from ``warehouse_dsl``):

    parse_task(source: str) -> Requirement
    canonicalize(source: str) -> str
    evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool

See ``README.md`` at the package root for the full grammar and the
finite-trace semantics of every construct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

__all__ = [
    "WarehouseSyntaxError",
    "Visit",
    "Avoid",
    "AvoidUntil",
    "Order",
    "Within",
    "Every",
    "AllOf",
    "AnyOf",
    "Requirement",
    "parse_task",
    "canonicalize",
    "evaluate_task",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WarehouseSyntaxError(ValueError):
    """Raised whenever ``source`` is not a well-formed program in the
    warehouse DSL: unknown constructs, wrong arity, malformed numbers or
    label sets, unbalanced brackets, or trailing input after a complete
    requirement.
    """


# ---------------------------------------------------------------------------
# Abstract syntax tree
#
# Every node is an immutable, hashable, frozen dataclass. Label sets are
# frozensets of labels; ordered lists of sub-requirements are tuples. The
# whole tree is therefore immutable, satisfying the ``parse_task`` contract.
# Each node implements two methods:
#   * ``holds(trace, cur)``   -- the finite-trace truth value, evaluated
#                                 with "the current step" set to ``cur``.
#   * ``to_source()``         -- canonical textual form (used by
#                                 ``canonicalize``).
# ---------------------------------------------------------------------------

LabelSet = frozenset  # frozenset[str]; kept as an alias for readability.


def _fmt_labelset(labels: "frozenset[str]") -> str:
    ordered = sorted(labels)
    if len(ordered) == 1:
        return ordered[0]
    return "{" + ", ".join(ordered) + "}"


@dataclass(frozen=True)
class Visit:
    """``visit(LabelSet)``

    Holds over a finite trace of length N, evaluated at current step
    ``cur``, iff there exists an index j with cur <= j < N such that
    trace[j] intersects ``labels``. This is "reach one of these labels at
    the current step or later" -- the current step counts.

    This is the language's only *unbounded* reachability construct, used
    both at the top level (cur = 0, "visit at least once, anywhere in the
    trace") and as an ``every(...)`` body ("after A, reach ..."). The
    contract's trigger-step convention is direction-specific, not
    uniformly exclusive: "evaluation begins at the trigger step" (the
    general nesting rule) makes the trigger step count, and the *only*
    place the contract excludes it is the explicit numeric offset in
    ``within`` ("does not include the trigger step"), which an author
    realizes by choosing a lower bound of 1. There is deliberately no
    separate unbounded "strictly after" construct: an earlier design had
    one, but it wrongly generalized ``within``'s numeric-offset exclusion
    to the unbounded case, rejecting traces the contract accepts (see
    README, "Worked example: the trigger step counts").
    """

    labels: "frozenset[str]"

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        n = len(trace)
        for j in range(max(cur, 0), n):
            if trace[j] & self.labels:
                return True
        return False

    def to_source(self) -> str:
        return f"visit({_fmt_labelset(self.labels)})"


@dataclass(frozen=True)
class Avoid:
    """``avoid(LabelSet)``

    Holds over a finite trace of length N, evaluated at current step
    ``cur``, iff for every index j with cur <= j < N, trace[j] does not
    intersect ``labels``. Vacuously true if cur >= N.
    """

    labels: "frozenset[str]"

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        n = len(trace)
        for j in range(max(cur, 0), n):
            if trace[j] & self.labels:
                return False
        return True

    def to_source(self) -> str:
        return f"avoid({_fmt_labelset(self.labels)})"


@dataclass(frozen=True)
class AvoidUntil:
    """``avoid_until(LabelSet, LabelSet)`` -- ``avoid_until(x_labels, c_labels)``

    Holds over a finite trace of length N, evaluated at current step
    ``cur``, iff:
      1. there exists a smallest index c* with cur <= c* < N such that
         trace[c*] intersects ``until_labels`` (a qualifying "C" at the
         current step or later), and
      2. for every index j with cur <= j < c*, trace[j] does not intersect
         ``avoid_labels`` (X is forbidden strictly before that C; the
         current step counts as part of "before C" exactly as step 0 would
         at the top level).

    X is allowed to co-occur with C at c* itself. If no qualifying C
    exists at or after cur, the requirement is False (an unfulfilled
    until-goal). Picking the smallest qualifying c* is always at least as
    permissive as any later choice, since the forbidden window only grows
    with a later C, so this is the unique witness that needs checking.
    """

    avoid_labels: "frozenset[str]"
    until_labels: "frozenset[str]"

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        n = len(trace)
        c_star = None
        for j in range(max(cur, 0), n):
            if trace[j] & self.until_labels:
                c_star = j
                break
        if c_star is None:
            return False
        for j in range(max(cur, 0), c_star):
            if trace[j] & self.avoid_labels:
                return False
        return True

    def to_source(self) -> str:
        return (
            f"avoid_until({_fmt_labelset(self.avoid_labels)}, "
            f"{_fmt_labelset(self.until_labels)})"
        )


@dataclass(frozen=True)
class Order:
    """``order(LabelSet, LabelSet, ...)`` with at least two steps.

    Holds over a finite trace of length N, evaluated at current step
    ``cur``, iff there exist strictly increasing indices
    cur <= j_1 < j_2 < ... < j_k < N such that trace[j_m] intersects
    ``steps[m]`` for every m. Irrelevant and repeated visits elsewhere in
    the trace are allowed; only the existence of *some* increasing witness
    sequence matters.
    """

    steps: Tuple["frozenset[str]", ...]

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        n = len(trace)
        pos = max(cur, 0) - 1
        for labels in self.steps:
            found = None
            for j in range(pos + 1, n):
                if trace[j] & labels:
                    found = j
                    break
            if found is None:
                return False
            pos = found
        return True

    def to_source(self) -> str:
        return "order(" + ", ".join(_fmt_labelset(s) for s in self.steps) + ")"


@dataclass(frozen=True)
class Within:
    """``within(lo, hi, LabelSet)`` optionally followed by ``then Requirement``.

    Holds over a finite trace of length N, evaluated at current step
    ``cur``, iff there exists an index j with cur+lo <= j <= cur+hi and
    0 <= j < N such that trace[j] intersects ``labels`` AND, if a
    ``followon`` is present, ``followon.holds(trace, j)`` is also True.

    Both bounds are inclusive and are counted as offsets from ``cur``
    (offset 0 is the current step itself; a lower bound of 1 excludes the
    current/trigger step, matching "N steps later, the trigger step does
    not count"). When several candidate steps fall in the window, any one
    of them may serve, and the follow-on (if any) is measured from
    whichever one is chosen -- so every in-window candidate is tried, and
    the whole node holds iff at least one candidate makes both the label
    hit and the follow-on succeed.
    """

    lo: int
    hi: int
    labels: "frozenset[str]"
    followon: Optional["Requirement"] = None

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        n = len(trace)
        lo_idx = cur + self.lo
        hi_idx = cur + self.hi
        for j in range(max(lo_idx, 0), min(hi_idx, n - 1) + 1):
            if trace[j] & self.labels:
                if self.followon is None or self.followon.holds(trace, j):
                    return True
        return False

    def to_source(self) -> str:
        base = f"within({self.lo}, {self.hi}, {_fmt_labelset(self.labels)})"
        if self.followon is None:
            return base
        return f"{base} then {self.followon.to_source()}"


@dataclass(frozen=True)
class Every:
    """``every(LabelSet, Requirement)``

    Holds over a finite trace of length N iff for every index i with
    0 <= i < N such that trace[i] intersects ``trigger``, ``body.holds``
    is True when evaluated with the current step set to i ("evaluation
    begins at the trigger step"). Vacuously true if the trigger never
    occurs anywhere in the trace. The ``cur`` this node itself is
    evaluated at is irrelevant to its own truth value: every occurrence in
    the whole trace is checked, matching "every time" / "each visit"
    phrasing.
    """

    trigger: "frozenset[str]"
    body: "Requirement"

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        for i, step in enumerate(trace):
            if step & self.trigger:
                if not self.body.holds(trace, i):
                    return False
        return True

    def to_source(self) -> str:
        return f"every({_fmt_labelset(self.trigger)}, {self.body.to_source()})"


@dataclass(frozen=True)
class AllOf:
    """``all_of(Requirement, Requirement, ...)`` with at least two parts.

    Holds iff every part holds, all evaluated at the same current step
    ``cur`` that this node itself receives.
    """

    parts: Tuple["Requirement", ...]

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        return all(part.holds(trace, cur) for part in self.parts)

    def to_source(self) -> str:
        return "all_of(" + ", ".join(p.to_source() for p in self.parts) + ")"


@dataclass(frozen=True)
class AnyOf:
    """``any_of(Requirement, Requirement, ...)`` with at least two parts.

    Holds iff at least one part holds, all evaluated at the same current
    step ``cur`` that this node itself receives.
    """

    parts: Tuple["Requirement", ...]

    def holds(self, trace: Tuple["frozenset[str]", ...], cur: int) -> bool:
        return any(part.holds(trace, cur) for part in self.parts)

    def to_source(self) -> str:
        return "any_of(" + ", ".join(p.to_source() for p in self.parts) + ")"


Requirement = Union[Visit, Avoid, AvoidUntil, Order, Within, Every, AllOf, AnyOf]


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_KEYWORDS = {
    "visit",
    "avoid",
    "avoid_until",
    "order",
    "within",
    "then",
    "every",
    "all_of",
    "any_of",
}


@dataclass(frozen=True)
class _Token:
    kind: str  # "KEYWORD" | "LABEL" | "NUMBER" | "LPAREN" | "RPAREN" | "LBRACE" | "RBRACE" | "COMMA" | "EOF"
    text: str
    pos: int


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
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "(":
            tokens.append(_Token("LPAREN", ch, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(_Token("RPAREN", ch, i))
            i += 1
            continue
        if ch == "{":
            tokens.append(_Token("LBRACE", ch, i))
            i += 1
            continue
        if ch == "}":
            tokens.append(_Token("RBRACE", ch, i))
            i += 1
            continue
        if ch == ",":
            tokens.append(_Token("COMMA", ch, i))
            i += 1
            continue
        if ch.isdigit():
            start = i
            while i < n and source[i].isdigit():
                i += 1
            tokens.append(_Token("NUMBER", source[start:i], start))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            text = source[start:i]
            if text[0].isupper():
                tokens.append(_Token("LABEL", text, start))
            else:
                tokens.append(_Token("KEYWORD_WORD", text, start))
            continue
        raise WarehouseSyntaxError(
            f"unexpected character {ch!r} at position {i}"
        )
    tokens.append(_Token("EOF", "", n))
    return tokens


# ---------------------------------------------------------------------------
# Parser (recursive descent, one token of lookahead)
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list):
        self._tokens = tokens
        self._i = 0

    def _peek(self) -> _Token:
        return self._tokens[self._i]

    def _advance(self) -> _Token:
        tok = self._tokens[self._i]
        self._i += 1
        return tok

    def _expect(self, kind: str) -> _Token:
        tok = self._peek()
        if tok.kind != kind:
            raise WarehouseSyntaxError(
                f"expected {kind} but found {tok.kind} {tok.text!r} at position {tok.pos}"
            )
        return self._advance()

    def _expect_keyword(self, word: str) -> _Token:
        tok = self._peek()
        if tok.kind != "KEYWORD_WORD" or tok.text != word:
            raise WarehouseSyntaxError(
                f"expected keyword {word!r} but found {tok.text!r} at position {tok.pos}"
            )
        return self._advance()

    def parse_program(self) -> Requirement:
        if self._peek().kind == "EOF":
            raise WarehouseSyntaxError("empty source: expected a requirement")
        node = self.parse_requirement()
        tail = self._peek()
        if tail.kind != "EOF":
            raise WarehouseSyntaxError(
                f"unexpected trailing input {tail.text!r} at position {tail.pos}"
            )
        return node

    def parse_requirement(self) -> Requirement:
        tok = self._peek()
        if tok.kind != "KEYWORD_WORD":
            raise WarehouseSyntaxError(
                f"expected a requirement keyword but found {tok.kind} {tok.text!r} "
                f"at position {tok.pos}"
            )
        if tok.text not in _KEYWORDS:
            raise WarehouseSyntaxError(
                f"unknown construct {tok.text!r} at position {tok.pos}"
            )
        if tok.text == "then":
            raise WarehouseSyntaxError(
                f"'then' may only follow a complete within(...) clause "
                f"(position {tok.pos})"
            )
        handler = {
            "visit": self._parse_visit,
            "avoid": self._parse_avoid,
            "avoid_until": self._parse_avoid_until,
            "order": self._parse_order,
            "within": self._parse_within,
            "every": self._parse_every,
            "all_of": self._parse_all_of,
            "any_of": self._parse_any_of,
        }[tok.text]
        return handler()

    # -- single-labelset constructs -----------------------------------

    def _parse_visit(self) -> Visit:
        self._expect_keyword("visit")
        self._expect("LPAREN")
        labels = self.parse_labelset()
        self._expect("RPAREN")
        return Visit(labels)

    def _parse_avoid(self) -> Avoid:
        self._expect_keyword("avoid")
        self._expect("LPAREN")
        labels = self.parse_labelset()
        self._expect("RPAREN")
        return Avoid(labels)

    def _parse_avoid_until(self) -> AvoidUntil:
        self._expect_keyword("avoid_until")
        self._expect("LPAREN")
        avoid_labels = self.parse_labelset()
        self._expect("COMMA")
        until_labels = self.parse_labelset()
        self._expect("RPAREN")
        return AvoidUntil(avoid_labels, until_labels)

    def _parse_order(self) -> Order:
        self._expect_keyword("order")
        self._expect("LPAREN")
        steps = [self.parse_labelset()]
        while self._peek().kind == "COMMA":
            self._advance()
            steps.append(self.parse_labelset())
        self._expect("RPAREN")
        if len(steps) < 2:
            raise WarehouseSyntaxError(
                "order(...) requires at least two steps"
            )
        return Order(tuple(steps))

    def _parse_within(self) -> Within:
        start_tok = self._expect_keyword("within")
        self._expect("LPAREN")
        lo_tok = self._expect("NUMBER")
        self._expect("COMMA")
        hi_tok = self._expect("NUMBER")
        self._expect("COMMA")
        labels = self.parse_labelset()
        self._expect("RPAREN")
        lo = int(lo_tok.text)
        hi = int(hi_tok.text)
        if lo < 0 or hi < 0:
            raise WarehouseSyntaxError(
                f"within(...) bounds must be non-negative (at position {start_tok.pos})"
            )
        if hi < lo:
            raise WarehouseSyntaxError(
                f"within(...) upper bound must be >= lower bound "
                f"(at position {start_tok.pos})"
            )
        followon = None
        if self._peek().kind == "KEYWORD_WORD" and self._peek().text == "then":
            self._advance()
            followon = self.parse_requirement()
        return Within(lo, hi, labels, followon)

    def _parse_every(self) -> Every:
        self._expect_keyword("every")
        self._expect("LPAREN")
        trigger = self.parse_labelset()
        self._expect("COMMA")
        body = self.parse_requirement()
        self._expect("RPAREN")
        return Every(trigger, body)

    def _parse_all_of(self) -> AllOf:
        self._expect_keyword("all_of")
        self._expect("LPAREN")
        parts = [self.parse_requirement()]
        while self._peek().kind == "COMMA":
            self._advance()
            parts.append(self.parse_requirement())
        self._expect("RPAREN")
        if len(parts) < 2:
            raise WarehouseSyntaxError("all_of(...) requires at least two parts")
        return AllOf(tuple(parts))

    def _parse_any_of(self) -> AnyOf:
        self._expect_keyword("any_of")
        self._expect("LPAREN")
        parts = [self.parse_requirement()]
        while self._peek().kind == "COMMA":
            self._advance()
            parts.append(self.parse_requirement())
        self._expect("RPAREN")
        if len(parts) < 2:
            raise WarehouseSyntaxError("any_of(...) requires at least two parts")
        return AnyOf(tuple(parts))

    # -- label sets ------------------------------------------------------

    def parse_labelset(self) -> "frozenset[str]":
        tok = self._peek()
        if tok.kind == "LABEL":
            self._advance()
            return frozenset({tok.text})
        if tok.kind == "LBRACE":
            self._advance()
            labels = []
            first = self._expect("LABEL")
            labels.append(first.text)
            while self._peek().kind == "COMMA":
                self._advance()
                nxt = self._expect("LABEL")
                labels.append(nxt.text)
            self._expect("RBRACE")
            if len(labels) != len(set(labels)):
                raise WarehouseSyntaxError(
                    f"duplicate label in label set near position {tok.pos}"
                )
            return frozenset(labels)
        raise WarehouseSyntaxError(
            f"expected a label or a {{...}} label set but found "
            f"{tok.kind} {tok.text!r} at position {tok.pos}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_task(source: str) -> Requirement:
    """Parse ``source`` into an immutable requirement tree.

    Raises ``WarehouseSyntaxError`` (a ``ValueError`` subclass) on any
    malformed source, including unknown constructs, wrong arity, malformed
    numeric bounds, malformed label sets, and trailing input.
    """

    if not isinstance(source, str):
        raise WarehouseSyntaxError("source must be a string")
    tokens = _tokenize(source)
    parser = _Parser(tokens)
    return parser.parse_program()


def canonicalize(source: str) -> str:
    """Return the canonical textual form of ``source``.

    Deterministic: the same input always produces the same output.
    Idempotent: ``canonicalize(canonicalize(s)) == canonicalize(s)`` for
    any well-formed ``s``, because the output is produced by a pure
    pretty-printer over the parsed tree, and the pretty-printer's own
    output re-parses to an identical tree.
    """

    tree = parse_task(source)
    return tree.to_source()


def evaluate_task(source: str, trace: "Tuple[frozenset, ...]") -> bool:
    """Parse ``source`` and evaluate it against ``trace``.

    ``trace`` is a finite ordered sequence of steps; each step is a set of
    proposition labels true at that step (index 0 is the first recorded
    step). Returns a plain ``bool``. A trace that ends before some visit,
    order, deadline, or until-goal required by the task can be completed
    evaluates to False rather than raising -- only malformed *source*
    raises.
    """

    tree = parse_task(source)
    return tree.holds(tuple(trace), 0)
