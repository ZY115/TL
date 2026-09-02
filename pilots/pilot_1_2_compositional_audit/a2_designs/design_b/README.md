# Warehouse DSL

A closed, standard-library-only Python implementation of a small
domain-specific language for authoring warehouse operating requirements
(pickup, inspection, delivery, charging, hazard avoidance) over finite
traces.

**Design seed tag: `22202`** (from `design_seed_tag.txt`; identifies this
design session, not a benchmark parameter).

## Trace model (fixed by `warehouse.md`)

A trace is a finite ordered sequence of **steps**, indexed from `0`. Each
step is a set of proposition labels (e.g. `A`, `B`, `X`); a label is *true*
at a step exactly when it is a member of that step's set. In this Python
package a trace is `tuple[frozenset[str], ...]`.

Every task written in this language evaluates to a plain `bool` against a
given trace. There is no third "error" outcome for evaluation: a trace that
leaves a required visit, order, deadline, or until-goal unresolved simply
evaluates to `False` (see `warehouse.md`, "An unfinished finite trace is
rejected..."). Malformed *source text*, by contrast, is rejected by
`parse_task` with an exception, never by returning a Boolean.

## Public API

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task

parse_task(source: str)                                    # -> immutable AST node
canonicalize(source: str) -> str                            # deterministic, idempotent
evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool
```

* `parse_task` tokenizes and parses `source`, returning the root of an
  immutable AST (frozen, hashable dataclasses; see `warehouse_dsl/core.py`).
  It raises `WarehouseDSLSyntaxError` or `WarehouseDSLValidationError` --
  both subclasses of `WarehouseDSLError`, itself a subclass of
  **`ValueError`** -- on anything that is not a fully well-formed program in
  the grammar below. Unknown heads, wrong arity, out-of-order bounds,
  reserved words used as labels, unbalanced parentheses, and trailing input
  are all rejected this way.
* `canonicalize` parses `source` and re-renders it in one fixed textual
  form: single-space-separated tokens, no comments, no incidental
  whitespace. It is **deterministic** (the same tree always prints the same
  string) and **idempotent** (`canonicalize(canonicalize(s)) ==
  canonicalize(s)`), because the canonical text is itself valid input that
  re-parses to an equal tree, and every node type has exactly one canonical
  rendering.
* `evaluate_task` parses `source` and evaluates it against `trace`,
  returning `bool`.

## Why this is a closed language, not an escape hatch

* No raw LTL formulas: there is no generic "next", "globally", "release",
  or "until-of-arbitrary-formula" operator, and no logical negation. Every
  construct below is a fixed, warehouse-specific idiom with its own
  hard-coded finite-trace rule.
* No `eval`, `exec`, callbacks, or imports: `warehouse_dsl` never executes
  anything from task source; the parser only ever builds data (dataclass
  instances), and the interpreter only ever walks that data.
* No serialization of an external IR: the concrete syntax (a small
  parenthesized keyword notation) and every keyword's semantics are defined
  from scratch in this document, in finite-trace terms, and nowhere else.
* Unknown constructs are rejected: any head word outside the nine listed
  below -- and any of those nine used in a position the grammar does not
  allow (e.g. `order` inside a `whenever` body) -- raises
  `WarehouseDSLValidationError` rather than being silently accepted or
  ignored.

## Grammar

Concrete syntax is a parenthesized, prefix keyword notation. Tokens are
`(`, `)`, integer literals (`[0-9]+`), and identifiers
(`[A-Za-z][A-Za-z0-9_]*`, used both for the nine reserved keywords and for
labels). `#` starts a comment that runs to end of line; comments and
whitespace are otherwise insignificant. A **label** is any identifier that
is not one of the nine reserved keywords.

There are two tiers of expression:

* **`requirement`** -- the whole task source is one `requirement`; it is
  also what `all_of` and top-level `either` combine.
* **`scoped`** -- the body of `whenever`, the body of `then`, and what a
  nested `either` combines. A `scoped` expression is always evaluated
  relative to a **scope start** step index, established by the innermost
  enclosing `whenever` (the trigger step) or `then` (the chosen step); at
  the outermost level of a task the scope start is `0`.

```
task        := requirement

requirement := "(" "visit" label+ ")"
             | "(" "never" label ")"
             | "(" "order" label label label* ")"        ; >= 2 labels
             | "(" "avoid_until" label label ")"
             | "(" "whenever" label scoped ")"
             | "(" "all_of" requirement requirement+ ")"  ; >= 2 children
             | "(" "either" requirement requirement+ ")"  ; >= 2 children

scoped      := "(" "visit" label+ ")"
             | "(" "avoid_until" label label ")"
             | "(" "within" int int label ")"
             | "(" "within" int int label "(" "then" scoped ")" ")"
             | "(" "either" scoped scoped+ ")"            ; >= 2 children

label       := identifier, not a reserved keyword
int         := "0" | [1-9][0-9]*                          ; bounds are nonnegative
```

Reserved keywords: `visit`, `never`, `order`, `avoid_until`, `whenever`,
`within`, `then`, `all_of`, `either`. `within`/`then` may only occur inside
a `whenever` body or a `then` body; `never`, `order`, `whenever`, and
`all_of` may only occur at the `requirement` tier (they cannot be nested
inside `whenever`/`then` -- no training card ever attaches a per-occurrence
"and", a bare "never", a nested "order", or a nested "whenever" to a
trigger, so the grammar does not manufacture those positions).

## Constructs, defined in finite-trace terms

Let a trace have steps `0 .. N-1`. "Scope start" `s` is `0` at the outer
level of a task, the trigger step for a `whenever` body, or the chosen step
for a `then` body (see below).

* **`(visit L1 L2 ... Ln)`** -- true iff at least one `Lk` occurs at some
  step `i` with `s <= i <= N-1`. One label is a plain "eventually visit
  L"; several labels is "eventually visit at least one of these" (an
  inclusive choice -- visiting more than one is fine). At the outer level
  `s = 0`, so this is "at some point during the run." Nested in a
  `whenever`/`then` scope, `s` is the trigger/chosen step, so this reads as
  "at or after that step" (the step itself counts).

* **`(never L)`** -- true iff `L` does not occur at *any* step `0 .. N-1`
  of the whole trace (this construct always inspects the entire run, never
  a sub-window; no card ever attaches "never" to a trigger).

* **`(order L1 L2 ... Ln)`** -- true iff there exist strictly increasing
  indices `s <= i1 < i2 < ... < in` with `Lk` at step `ik`, for every `k`.
  Irrelevant steps and repeated visits elsewhere are allowed, and an early
  occurrence of some `Lk` never "uses up" or blocks a later one: the
  requirement is existential over the whole set of valid increasing index
  choices, not tied to the first match. (Implemented by a greedy
  earliest-next-match scan, which is exactly equivalent to that
  existential reading for a plain increasing-index search.)

* **`(avoid_until X C)`** -- true iff some step `c` with `s <= c <= N-1`
  carries `C`, and `X` does not occur at any step `i` with `s <= i < c`
  for the *earliest* such `c`. (Choosing the earliest qualifying `C`
  is always at least as good as any later one, since it minimizes the
  forbidden window -- so "there exists a qualifying `C`" and "the earliest
  `C` qualifies" coincide.) `X` is allowed on the `C` step itself, and, if
  nested, `X` is also allowed strictly before the scope start `s`. If no
  `C` occurs at or after `s`, the requirement is unfulfilled and this
  evaluates to `False`.

* **`(within LO HI L)`** -- true iff some step `j` with `s+LO <= j <= s+HI`
  (and `j <= N-1`) carries `L`. Both bounds are inclusive; `LO=0` would
  allow the scope-start step itself, and (matching every training card)
  `LO>=1` excludes it. `LO` and `HI` are plain nonnegative integers with
  `LO <= HI` (a parse-time check).

* **`(within LO HI L (then SCOPED))`** -- true iff some step `j` in the
  same window as above carries `L` **and** `SCOPED` holds with its own
  scope start set to that `j`. If several steps in the window carry `L`,
  any one of them may be used, but `SCOPED` is measured from whichever one
  is chosen -- so the interpreter tries every `L`-bearing step in the
  window (there are at most `HI-LO+1` of them) and succeeds if any choice
  makes `SCOPED` hold. This matters because the best choice is not always
  the earliest one: a later `L` step can shrink an `avoid_until` follow-on's
  forbidden window enough to admit an `X` that would have broken an earlier
  choice (see `tests/test_warehouse_dsl.py`,
  `test_within_then_backtracks_over_candidate_choice`, for a worked case).

* **`(whenever T SCOPED)`** -- true iff, for *every* step `i` (over the
  whole trace) at which `T` occurs, `SCOPED` holds with scope start `s=i`.
  If `T` never occurs anywhere in the trace, this is vacuously `True`.
  (`whenever` is never nested inside another `whenever`/`then`: each
  trigger occurrence is independent and always scans the whole trace for
  itself.)

* **`(all_of R1 R2 ... Rn)`** -- true iff every `Rk` holds (each evaluated
  at the outer scope start it receives -- `0` unless `all_of` itself sits
  inside a `whenever`/`then`, which the grammar does not permit, so in
  practice always `0`).

* **`(either N1 N2 ... Nn)`** -- true iff at least one `Nk` holds, all
  evaluated at the *same* scope start as the `either` node itself.
  Completing more than one is fine (inclusive or). Valid both as a
  `requirement` (combining whole alternative plans, e.g. train_13) and as
  a `scoped` clause (combining per-occurrence options that share one
  trigger/chosen step, e.g. train_16).

## Mapping from the training cards

| Card | Source (in `training_artifacts/`) |
|------|-------------------------------------|
| train_01 | `(visit A)` |
| train_02 | `(never X)` |
| train_03 | `(order A B)` |
| train_04 | `(whenever A (within 1 4 B))` |
| train_05 | `(avoid_until X C)` |
| train_06 | `(whenever A (visit B C))` |
| train_07 | `(all_of (visit A) (never X))` |
| train_08 | `(order A B C)` |
| train_09 | `(whenever B (avoid_until X C))` |
| train_10 | `(visit B D)` |
| train_11 | `(whenever A (within 1 3 B (then (visit C))))` |
| train_12 | `(whenever A (within 1 2 B (then (avoid_until X C))))` |
| train_13 | `(either (all_of (order A B) (never X)) (visit D))` |
| train_14 | `(whenever C (within 2 4 D))` |
| train_15 | `(all_of (order C D) (whenever C (within 1 5 D)))` |
| train_16 | `(whenever A (either (within 1 2 B (then (visit C))) (visit D)))` |

Every one of the nine keywords, and every nesting position permitted by the
grammar, is exercised by at least one of these sixteen sources; the grammar
adds no construct and no nesting position that the cards do not call for
(see "Design notes" below).

## Design notes

* **Two tiers, not one.** Cards 4, 6, 9, 11, 12, 14, and 16 all attach a
  per-occurrence requirement to a trigger ("every time A ..."), and cards
  11, 12, and 16 further attach a follow-on to a bounded step inside that
  window ("... and then ..."). Cards 7, 13, and 15 combine whole
  requirements with top-level "and"/"or". No card ever nests `order`,
  `never`, `whenever`, or a per-occurrence `all_of` inside a trigger's
  scope, so the grammar keeps `requirement` and `scoped` separate instead
  of flattening everything into one fully general recursive tree.
* **`visit` and `either` are shared across tiers** because their
  finite-trace rule ("at least one of these holds, from the same scope
  start") is identical in both places; only the scope start they are
  handed differs, and that is threaded through by the interpreter, not
  hard-coded per tier.
* **`either` is n-ary**, not just binary, even though every card uses
  exactly two branches: this is the same disjunction card 13 and card 16
  already ask for, just not artificially capped at two. The same is true of
  `all_of`, `visit`, and `order`. No new combinator was introduced to get
  this; existing ones were simply not given an arbitrary arity limit the
  cards never motivate.
* **No negation, no bare scoped `never`/`order`.** Every card is phrased as
  a positive visit, a whole-trace avoidance, an ordering, a bounded
  deadline, an until-goal, or a choice/conjunction of those -- never as
  "it is not the case that ..." applied to a sub-requirement, and never as
  an avoidance or ordering that only kicks in after a trigger. Adding
  general negation would also risk reintroducing arbitrary propositional
  logic (i.e. drifting toward raw LTL), which the assignment rules out.

## Package layout

```
warehouse_dsl/
    __init__.py   -- exports parse_task, canonicalize, evaluate_task, node
                      types, and the exception hierarchy
    core.py        -- tokenizer, recursive-descent parser, immutable AST
                      (frozen dataclasses), canonical printer, interpreter
training_artifacts/
    train_01.wdsl .. train_16.wdsl  -- one source per training card
tests/
    test_warehouse_dsl.py           -- unittest suite (parsing, rejection,
                                        canonicalization, and semantics,
                                        including direct per-card checks)
```

## Running the tests

```bash
cd a2_designs/design_b
python3 -m unittest discover -s tests -v
```

All 76 tests pass on CPython's standard library alone (no third-party
dependencies).
