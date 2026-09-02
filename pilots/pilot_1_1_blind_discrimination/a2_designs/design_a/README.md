# Warehouse suffix-task DSL

This package implements a small closed language for finite warehouse traces.
It uses nested S-expressions so composition is visible while every proposition
label and numeric bound remains in the task source. It uses only the Python
standard library.

The independent design seed tag supplied for this design session is **11101**.
The tag identifies the design session only; it has no effect on parsing or
evaluation.

## Public API

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task
```

`parse_task(source)` parses exactly one expression and returns an immutable
`Task`. `canonicalize(source)` returns the unique single-line spelling of the
same task. `evaluate_task(source, trace)` parses the source and returns a
Boolean. A trace must be a `tuple` whose steps are `frozenset[str]` values.
Malformed source, extra expressions, unknown constructs, or unknown argument
shapes are rejected with `DSLParseError` (a `ValueError` subclass). Malformed
API value types are rejected with `TypeError`.

## Lexical and trace conventions

Whitespace may separate tokens and has no semantic effect. Parentheses are
structural. Labels are unquoted and must match
`[A-Za-z_][A-Za-z0-9_.-]*`. Bounds are nonnegative decimal integers. There are
no comments, aliases, variables, user-defined operators, callbacks, imports,
or other escape mechanisms.

A trace is `s[0], ..., s[n-1]`, and label `P` is true at index `i` exactly when
`P in s[i]`. Every expression is evaluated at an **origin** index. The complete
task starts at origin 0. The construct `after-each` can evaluate a child at a
later origin. All intervals below are inclusive unless explicitly stated
otherwise. A required index beyond the finite trace does not exist and cannot
satisfy a requirement.

## Complete grammar

```text
task ::= (eventually LABEL)
       | (never LABEL)
       | (sequence LABEL LABEL ...)
       | (within NONNEGATIVE_INTEGER NONNEGATIVE_INTEGER LABEL)
       | (avoid-until LABEL LABEL)
       | (after-each LABEL task)
       | (all task task ...)
       | (any task task ...)
```

`sequence`, `all`, and `any` each require at least two arguments. For `within`,
the lower bound must not exceed the upper bound.

## Finite-trace meaning of every construct

For an expression evaluated at origin `o`:

- `(eventually P)` is true exactly when some index `i >= o` contains `P`.
  Thus the origin step itself is eligible. It is false on an empty remaining
  suffix.
- `(never P)` is true exactly when no index `i >= o` contains `P`. It is true
  on an empty remaining suffix.
- `(sequence P1 P2 ... Pk)` is true exactly when there are strictly increasing
  indices `o <= i1 < i2 < ... < ik < n` with `Pj` at `ij`. Other labels,
  irrelevant steps, early out-of-order labels, and repeated labels do not
  matter. The strict inequalities mean two milestones cannot use the same
  trace position.
- `(within lower upper P)` is true exactly when `P` occurs at some index
  `o + d` for `lower <= d <= upper`. Offset zero denotes the origin step;
  offset one denotes the immediately following step. An occurrence before the
  lower bound does not prevent a later in-window occurrence from satisfying
  the construct.
- `(avoid-until X G)` is true exactly when a selectable endpoint `j >= o`
  contains `G` and `X` is absent at every index `i` with `o <= i < j`. `X` is
  allowed at endpoint `j`, including when `X` and `G` coincide. If `G` is at
  the origin, there are no strictly earlier suffix steps to check. It is false
  when no endpoint is reached in the finite suffix.
- `(after-each T child)` is true exactly when, for every index `i >= o` that
  contains `T`, `child` is true with its origin changed to `i`. One child
  success may satisfy multiple triggers when its own semantics allow that. If
  there is no `T` in the suffix, the construct is vacuously true.
- `(all child1 child2 ... childk)` is true exactly when every child is true at
  the same origin.
- `(any child1 child2 ... childk)` is true exactly when at least one child is
  true at the same origin.

The language deliberately separates strict milestone order (`sequence`) from
offset timing (`within`) and current-or-later suffix goals (`eventually` and
`avoid-until`). This makes uses of words such as “later,” “next,” and “until”
explicit instead of relying on parser conventions.

## Examples and artifacts

```text
(all (eventually A) (never X))
(after-each A (within 1 4 B))
(after-each B (avoid-until X C))
```

The 14 independently authored task sources are in `training_artifacts/`. Run
the focused standard-library test suite from this directory with:

```bash
python3 -m unittest discover -s tests -v
```
