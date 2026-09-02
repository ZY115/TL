# Windowed Warehouse DSL

Design seed tag: **22202**

This directory is a self-contained, standard-library-only Python package for a
closed finite-trace task language. A task source names every proposition,
numeric bound, alternative, and nesting relation on which its result depends.
There are no includes, macros, callbacks, imports, embedded formulas, or escape
hatches.

## Public API

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task
```

- `parse_task(source: str)` validates the complete source and returns an
  immutable `Task` syntax tree. Invalid or unknown syntax raises
  `DSLSyntaxError`, a `ValueError` subclass.
- `canonicalize(source: str) -> str` parses and emits a deterministic,
  two-space-indented representation ending in one newline.
- `evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool`
  evaluates a source on the supplied finite trace.

Only the Python standard library is used. Run the test suite from this
directory with:

```sh
python3 -m unittest discover -s tests -v
```

## Lexical and trace conventions

A proposition label matches `[A-Za-z][A-Za-z0-9_]*`; labels and keywords are
case-sensitive. An integer is a nonnegative decimal integer. Whitespace has no
meaning. Comments are deliberately not part of the language.

A trace is a tuple of frozensets of string labels. Its positions are numbered
from zero. To define nesting precisely, every expression is evaluated over an
*active window* `[s, e]`, inclusive. The root window is
`[0, len(trace) - 1]`; it is empty when the trace is empty. Unless a construct
below changes the window, it passes the same window to its children.

## Complete grammar

```text
task       ::= expression
expression ::= "seen" label
             | "never" label-list
             | "order" label-list
             | "until" label "avoiding" label-list
             | "within" integer ".." integer "{" expression "}"
             | "after" label "{" expression "}"
             | "all" "{" expression (";" expression)* ";"? "}"
             | "any" "{" expression (";" expression)* ";"? "}"
label-list ::= "[" label ("," label)* "]"
```

Label lists and Boolean blocks must be nonempty. An `order` list must contain
at least two labels. Duplicate labels are rejected in the set-like `never` and
`until` lists. They are allowed in `order`, where `order [A, A]` requires two
strictly separated occurrences of `A`. A `within` lower bound must not exceed
its upper bound. No token or construct beyond this grammar is accepted.

## Finite-trace semantics

The following definitions apply on an active window `[s, e]`. A range with
`s > e` is empty.

- `seen A` is true exactly when `A` occurs at some index in `[s, e]`. It is
  false on an empty window, so an unfinished required visit is rejected.
- `never [X, Y]` is true exactly when none of the listed labels occurs at any
  index in `[s, e]`. It is true on an empty window.
- `order [A, B, C]` is true exactly when indices `i_A < i_B < i_C` exist in
  `[s, e]` with the corresponding label at each position. Extra and repeated
  visits are ignored. A label at the same step as the preceding milestone
  cannot complete the next milestone. Failure to finish the sequence is false.
- `until C avoiding [X, Y]` is true exactly when some selected endpoint
  `k` in `[s, e]` contains `C` and none of the forbidden labels occurs in
  `[s, k-1]`. Forbidden labels are allowed at the endpoint `k`, including on a
  step that also contains `C`. A missing endpoint is false.
- `within L..U { E }` evaluates `E` on
  `[s+L, min(s+U, e)]`. Both offsets are inclusive. Thus, under an `after A`,
  `within 1..4 { seen B }` considers precisely the first through fourth steps
  after each `A`, excluding the trigger step. Clipping never extends a finite
  trace; an unsatisfied visit in a clipped or empty deadline window is false.
- `after A { E }` finds every occurrence of `A` in `[s, e]`. For each trigger
  index `i`, it requires `E` on the suffix window `[i, e]`. It is true when no
  `A` occurs. Consequently, nested `until` begins at the trigger step, while a
  nested `within` measures offsets from that same step.
- `all { E1; E2; ...; }` is conjunction: all children are evaluated on the
  same active window and must be true.
- `any { E1; E2; ...; }` is disjunction: at least one child, evaluated on the
  same active window, must be true.

These definitions are Boolean on complete finite traces. In particular,
missing `seen`, `order`, `until`, or deadline witnesses reject the trace;
triggered `after` obligations are vacuous only when their trigger is absent.

## Training artifacts

`training_artifacts/train_01.task` through `train_14.task` are independently
authored complete programs corresponding by number to the supplied cards. They
are ordinary DSL sources and contain no references to hidden configuration.
