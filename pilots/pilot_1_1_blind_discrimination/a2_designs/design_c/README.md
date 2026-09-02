# Warehouse DSL, design C

Design seed tag: **33303**. The tag records this independent design session;
it has no effect on parsing or evaluation.

Warehouse DSL is a small, closed language for finite warehouse traces. A task
is one expression. Its entire meaning, including proposition names, numerical
bounds, branch choices, and nesting, is present in that source expression.
There are no includes, callbacks, imports, hidden task tables, or general code
escape hatches.

## Trace and anchor convention

A trace is a tuple of `frozenset[str]` steps. Step 0 is the first recorded
step. A proposition is true exactly when its label belongs to that step's set.

Every expression is evaluated at an **anchor**. At the top level the anchor is
0. `after_each` changes the anchor to a trigger's step; the other combinators
pass their anchor unchanged. Thus words such as "visit", "avoid", and
"sequence" mean from the current anchor through the finite end of the trace.
All decisions are Boolean. Missing required endpoints, visits, ordered
milestones, or deadline witnesses make a finished finite trace false.

## Grammar

Whitespace may occur between tokens and is otherwise insignificant. Labels
are unquoted identifiers matching `[A-Za-z_][A-Za-z0-9_]*`. Bounds are decimal
integers from 0 through 1,000,000,000. Trailing commas are not accepted.

```text
task ::= expression

expression ::=
    visit(label)
  | avoid(label)
  | sequence(label, label, ...)
  | between(lower, upper, label)
  | avoid_until(forbidden_label, goal_label)
  | after_each(trigger_label, expression)
  | all(expression, expression, ...)
  | any(expression, expression, ...)
```

`sequence`, `all`, and `any` each require at least two arguments. In
`between`, `lower` must not exceed `upper`. The parser rejects unknown
constructs and any source that does not match this grammar.

## Finite-trace semantics

Below, `k` is the current anchor and `n` is the trace length.

### `visit(P)`

True exactly when `P` occurs at some index `i` with `k <= i < n`. The anchor
step is included. With no such occurrence (including an empty suffix), it is
false.

### `avoid(P)`

True exactly when `P` occurs at no index `i` with `k <= i < n`. It is true on
an empty suffix.

### `sequence(P1, P2, ..., Pm)`

True exactly when indices `i1 < i2 < ... < im` exist, all at or after `k`, and
`Pj` occurs at `ij`. Irrelevant and repeated visits are allowed. One step that
contains two requested labels cannot serve as both positions. The evaluator
uses the earliest possible witness greedily, which is equivalent to existence
for this ordered-subsequence condition.

### `between(lo, hi, P)`

True exactly when `P` occurs at an existing index `k + d` for at least one
inclusive offset `lo <= d <= hi`. Offset 0 denotes the anchor step. An
occurrence earlier than `lo` is ignored and does not prevent a qualifying
later one. If the finite trace ends before any qualifying occurrence, the
result is false.

For example, `after_each(A, between(1, 4, B))` says that every `A` has a `B`
one, two, three, or four steps later. The trigger step is excluded because the
lower bound is 1.

### `avoid_until(X, G)`

True exactly when a selected goal index `j >= k` exists where `G` occurs, and
`X` is absent at every index `i` with `k <= i < j`. The goal endpoint is not
part of the forbidden interval, so `X` and `G` may coexist at `j`. The goal may
be at the anchor itself. Without a qualifying goal before the finite trace
ends, the result is false.

### `after_each(T, R)`

For every index `j >= k` containing `T`, evaluate `R` with anchor `j`; all such
evaluations must be true. If no `T` occurs in the suffix, the result is
vacuously true. Each repeated trigger creates an independent obligation.

### `all(R1, R2, ..., Rm)`

Evaluate every child at the same anchor. True exactly when all children are
true. This represents mandatory conjunction without changing their scopes.

### `any(R1, R2, ..., Rm)`

Evaluate every child at the same anchor. True exactly when at least one child
is true. A different successful alternative may witness each enclosing
`after_each` trigger.

## Public Python API

The package uses only the Python standard library and exposes:

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task

tree = parse_task("all(visit(A), avoid(X))")
text = canonicalize(" all ( visit(A),avoid(X) ) ")
ok = evaluate_task(
    "all(visit(A), avoid(X))",
    (frozenset(), frozenset({"A"})),
)
```

`parse_task(source)` returns immutable dataclass nodes and raises
`DSLParseError` (a `ValueError`) for invalid language source.
`canonicalize(source)` first validates and then emits a deterministic
single-line spelling. `evaluate_task(source, trace)` parses and evaluates a
task, returning a `bool`; it requires the exact trace container convention
`tuple[frozenset[str], ...]`.

## Training artifacts and tests

`training_artifacts/train_01.wdsl` through `train_14.wdsl` are independently
authored task sources corresponding to the supplied natural-language cards.
Run the focused tests from this directory with:

```sh
python3 -m unittest discover -s tests -v
```

