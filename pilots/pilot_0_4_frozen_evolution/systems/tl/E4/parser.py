"""E4 Core-TL RULE parser with strong Until support."""

from __future__ import annotations

import re

from .syntax import (
    Always,
    And,
    Atom,
    BoundedEventually,
    Eventually,
    Formula,
    Implies,
    Not,
    Or,
    Until,
)

TOKEN_PATTERN = re.compile(r"F|G|[A-Za-z_][A-Za-z_0-9]*|\d+|->|[!&|(),\[\]]")


class Parser:
    def __init__(self, source: str):
        self.tokens = TOKEN_PATTERN.findall(source)
        self.position = 0

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError(f"Expected {expected!r}, found {token!r}")
        self.position += 1
        return token

    def parse(self) -> Formula:
        formula = self.parse_implication()
        if self.peek() is not None:
            raise ValueError(f"Unexpected token: {self.peek()!r}")
        return formula

    def parse_implication(self) -> Formula:
        left = self.parse_or()
        if self.peek() == "->":
            self.take("->")
            return Implies(left, self.parse_implication())
        return left

    def parse_or(self) -> Formula:
        formula = self.parse_until()
        while self.peek() == "|":
            self.take("|")
            formula = Or(formula, self.parse_until())
        return formula

    def parse_until(self) -> Formula:
        formula = self.parse_and()
        while self.peek() == "U":
            self.take("U")
            formula = Until(formula, self.parse_and())
        return formula

    def parse_and(self) -> Formula:
        formula = self.parse_unary()
        while self.peek() == "&":
            self.take("&")
            formula = And(formula, self.parse_unary())
        return formula

    def parse_unary(self) -> Formula:
        token = self.peek()
        if token == "!":
            self.take("!")
            return Not(self.parse_unary())
        if token == "G":
            self.take("G")
            return Always(self.parse_unary())
        if token == "F":
            self.take("F")
            if self.peek() == "[":
                self.take("[")
                lower = int(self.take())
                self.take(",")
                upper = int(self.take())
                self.take("]")
                return BoundedEventually(lower, upper, self.parse_unary())
            return Eventually(self.parse_unary())
        if token == "(":
            self.take("(")
            formula = self.parse_implication()
            self.take(")")
            return formula
        if token is None or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token):
            raise ValueError(f"Expected atom, found {token!r}")
        return Atom(self.take())


def parse_rule(source: str) -> Formula:
    return Parser(source).parse()
