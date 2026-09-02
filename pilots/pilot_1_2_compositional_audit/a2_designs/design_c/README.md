# Warehouse DSL

Design seed tag: **33303** (from `design_seed_tag.txt`, recorded here per
the design instructions; it identifies this design session and is not a
benchmark parameter).

A small closed language for authoring warehouse operating requirements --
pickup, inspection, delivery, charging, hazard avoidance -- as they are
described in the training task cards. A task source is a single
requirement built from eight constructs over labeled steps of a finite
trace. There is no raw LTL, no `eval`/`exec`, no imports, no arbitrary
Python callback, and no serialization of any other formula language:
every construct below is defined directly against the finite-trace
contract, and the grammar in this document is the complete surface of the
language. Unknown constructs are rejected by the parser.

## Trace model (fixed by `warehouse.md`)

A trace is a finite tuple of steps, `trace[0], trace[1], ..., trace[n-1]`.
Each step is a `frozenset[str]` of proposition labels true at that step
(e.g. `{"A"}`, or `{"B", "X"}` if two things are true at once). A label is
true at a step exactly when it is a member of that step's set.

Every construct below is evaluated with a **start index** `s`: the point
from which "at or after" and "strictly before/after" are measured. At the
top level `s = 0`. Nested constructs set `s` to a specific step, as
described per-construct below.

## Grammar

```
task         ::= requirement

requirement  ::= "visit" "(" target ")"
               | "avoid" "(" target ")"
               | "order" "(" target ("," target)+ ")"
               | "within" "(" target "," integer "," integer
                            ("," "then" "=" requirement)? ")"
               | "avoid_until" "(" target "," target ")"
               | "every" "(" target "," requirement ")"
               | "and" "(" requirement ("," requirement)+ ")"
               | "or" "(" requirement ("," requirement)+ ")"

target       ::= label
               | "any" "(" label ("," label)+ ")"

label        ::= identifier, excluding the reserved words below
integer      ::= digit+                      ; unsigned, base 10
identifier   ::= [A-Za-z_][A-Za-z0-9_]*

reserved words: visit avoid order within then avoid_until every and or any
comments:    "#" to end of line (stripped; carry no meaning)
whitespace:  insignificant between tokens
```

A task source is exactly one `requirement`. Trailing text after a
complete requirement is a syntax error, as is any identifier in
requirement/target position that is not one of the keywords above --
this is how "unknown constructs must be rejected" is enforced: the
keyword set is closed and checked explicitly, there is no fallback or
escape path.

`order(...)`, `and(...)`, `or(...)`, and `any(...)` all require at least
two children/labels (arity is checked at parse time and raises
`WarehouseValidationError`, a `ValueError` subclass, if violated). This
is why, for instance, a single-target `order(A)` is rejected: it is not a
meaningful ordering constraint, and the author should write `visit(A)`
instead.

## Constructs, in finite-trace terms

Let `n = len(trace)`. "Matches" for a `target` at step `trace[j]` means:
the label is in `trace[j]` (a bare `label`), or at least one of the
labels is in `trace[j]` (`any(l1, ..., lk)`).

- **`visit(target)`**, evaluated at start `s`: true iff there exists `j`
  with `s <= j < n` such that `target` matches `trace[j]`. This is
  "eventually `target`, at or after `s`"; at the top level (`s = 0`) it
  is `target` reached anywhere in the run.

- **`avoid(target)`**, evaluated at start `s`: true iff for every `j`
  with `s <= j < n`, `target` does not match `trace[j]`. This is
  "`target` never holds, at or after `s`"; at the top level it is a
  whole-run prohibition.

- **`order(t1, t2, ..., tk)`**, `k >= 2`, evaluated at start `s`: true
  iff there exist indices `s <= i1 < i2 < ... < ik < n` with `t_m`
  matching `trace[i_m]` for every `m`. Indices must be *strictly*
  increasing; an occurrence of `t_m` that precedes the chosen `i_(m-1)`
  cannot be reused to satisfy position `m`. Irrelevant and repeated
  visits elsewhere in the trace are allowed and do not interfere.

- **`within(target, lo, hi[, then=requirement])`**, `0 <= lo <= hi`,
  evaluated at start `s`: true iff there exists `j` with
  `s + lo <= j <= s + hi` (and `0 <= j < n`) such that `target` matches
  `trace[j]`, **and**, if a `then` clause is present, `then` holds when
  evaluated with start `j`. `lo` and `hi` are both inclusive, and `lo`
  steps are counted from `s` -- so `lo = 1` excludes `s` itself ("the
  trigger step does not count"), while `lo = 0` would allow `j = s`. If
  several steps in the window match `target`, any one of them may be
  used, but `then` (if present) is measured beginning at whichever one
  is chosen -- the implementation searches every matching step in the
  window and accepts if *any* of them makes the whole construct true, so
  a candidate that fails its own `then` does not block a later candidate
  in the same window from succeeding (see `tests/test_warehouse_dsl.py`,
  `test_within_then_avoid_until_needs_existential_search`, for a
  concrete case where the first candidate fails and only the second
  succeeds). Without `then`, this is a plain bounded deadline.

- **`avoid_until(avoid_target, reach_target)`**, evaluated at start `s`:
  let `j0` be the smallest `j >= s` such that `reach_target` matches
  `trace[j]`. False if no such `j0` exists (the reach is required, not
  optional, even at the end of a finite trace). Otherwise, true iff
  `avoid_target` does not match `trace[k]` for any `k` with
  `s <= k < j0`. `avoid_target` is checked starting *at* `s` (inclusive)
  through the step immediately before `j0` -- it is explicitly allowed
  to match at `j0` itself (the "endpoint"). When nested inside `every`
  or a `within(...).then`, `s` is the trigger/chosen step, so the
  avoidance window begins at that step, not at the start of the trace.

- **`every(trigger, body)`**, evaluated independent of any inherited
  start (it always scans the whole trace for its trigger): let
  `I = {i : 0 <= i < n, trigger matches trace[i]}`. If `I` is empty, true
  vacuously. Otherwise true iff `body` holds when evaluated with start
  `i`, for *every* `i` in `I` independently -- each triggering step gets
  its own fresh evaluation of `body`, so different occurrences of
  `trigger` may satisfy `body` in different ways (this matters for
  `body` containing `or`, as in `train_16`).

- **`and(r1, ..., rk)`**, `k >= 2`, evaluated at start `s`: true iff
  every `r_m` holds when evaluated at start `s`.

- **`or(r1, ..., rk)`**, `k >= 2`, evaluated at start `s`: true iff at
  least one `r_m` holds when evaluated at start `s`. Non-exclusive: more
  than one disjunct may hold.

`evaluate_task` returns `_eval(tree, trace, 0)` -- a plain `bool`. A
finite trace that has not (yet) discharged some pending visit, order,
deadline, or until-goal evaluates to `False`; per the required API
contract there is no separate "unfinished" signal, and `warehouse.md`'s
"an unfinished trace is rejected" is realized as that overall `False`.

## Why these eight constructs and no others

Every construct is required by at least one training card; none was
added speculatively:

| Construct | First needed by | Card language |
|---|---|---|
| `visit` | train_01 | "visit ... at least once before the run ends" |
| `avoid` | train_02 | "never enter the hazard zone X" |
| `order` (binary) | train_03 | "visit A and, at a strictly later step, visit B" |
| `order` (n-ary) | train_08 | "visit A, then B, then C at strictly increasing steps" |
| `within` (no `then`) | train_04 | "reach B between one and four steps later, inclusive" |
| `avoid_until` | train_05 | "stay out of the hazard zone X until it reaches ... C" |
| `any(...)` targets | train_06, train_10 | "at least one of the two packing stations B or C/D" |
| `and` | train_07 | "visit A ..., and it must never enter ... X" |
| `every` | train_04, 06, 09, 11, 12, 14, 16 | "Every time the robot visits/picks up at ..." |
| `within(...).then` | train_11 | "reach B ... and after that inspection it must eventually reach ... C. The C must come at or after the B chosen" |
| `or` | train_13, train_16 | "at least one of these two plans", "one of two options" |

`order` is a single n-ary primitive (not a chain of binary combinators)
because train_03 needs `k = 2` and train_08 needs `k = 3`; generalizing
the arity is not a new construct, just not capping one unnecessarily.
Likewise `and`/`or` are n-ary rather than strictly binary, and a
`target` (bare label or `any(...)` group) is used uniformly everywhere a
label can appear -- including inside `avoid`/`avoid_until`'s
avoid-slot, which no card exercises with more than one label -- because
introducing a second, more restricted "label-only" grammar rule just for
those slots would be an extra special case the cards give no reason to
add, not a simplification.

Two deliberate omissions:

- **No unbounded upper bound on `within`.** Every bounded deadline in the
  cards (train_04, 11, 12, 14, 15, 16) gives an explicit finite `hi`.
  The one place an unbounded-but-lower-bounded reach appears
  (train_05/09's "current step or later", train_11's "at or after the B
  chosen", train_16's "at that pickup step or later") is exactly what
  `visit`, evaluated from the relevant start index, already means -- so
  it is expressed with `visit`/`avoid_until`, not with a `within` that
  has an infinite `hi`. Adding an infinity token to `within` would
  duplicate `visit` for a case no card needs.
- **No `then` on `avoid_until`.** No card chains a further requirement
  after an avoid-until's reach step, so `avoid_until` has no follow-on
  slot. (`within(...).then` can itself be an `avoid_until`, which is
  exactly train_12/16's shape, and already covers "reach, then avoid
  until".)

## A reading decision worth flagging: train_06's "afterwards"

Train_06 says a packing station must be reached "afterwards", with no
explicit "strictly" and no explicit "at or after" qualifier -- unlike
every other relative-timing phrase in the card set, which is always one
or the other (train_03/08 say "strictly"; train_04/11/12/14/15/16 give
explicit numeric bounds with `lo >= 1`, which excludes the trigger step
by construction; train_05/09/11/16 say "at the current/that step or
later" or "at or after"). Since the language already needs exactly one
unbounded-reach primitive (`visit`, used from a given start index, and
confirmed inclusive-of-start by train_05, train_09, train_11's `then`,
and train_16's second option), train_06 is read as invoking that same
primitive rather than motivating a second, stricter unbounded-reach
construct that no other card needs. Concretely: `every(A, visit(any(B,
C)))` allows a packing station visit to coincide with the same step as
the pickup. This is documented here, and exercised directly by a test
(`test_every_visit_allows_same_step_as_trigger`), so the interpretation
is auditable rather than silent.

## API

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task
```

- **`parse_task(source: str)`** -- tokenizes and parses `source`,
  returning the root `Requirement` node of an immutable tree (frozen,
  hashable dataclasses throughout; tuples, never lists, hold ordered
  children). Raises `WarehouseSyntaxError` on a tokenizing/grammar
  failure (unrecognized character, unknown construct, missing/extra
  punctuation, trailing text) or `WarehouseValidationError` on a
  well-formed-but-invalid tree (`lo > hi`, too few children in
  `order`/`and`/`or`/`any`, a reserved word used as a label). Both are
  subclasses of `WarehouseDSLError`, itself a `ValueError` subclass.

- **`canonicalize(source: str) -> str`** -- parses `source` and
  pretty-prints the resulting tree in one fixed style: single line,
  comments and extra whitespace removed, integer literals rendered
  without leading zeros, one space after each comma, and no trailing
  space. Formatting is a pure function of the parsed tree, and parsing
  the canonical style reproduces the same tree, so
  `canonicalize(canonicalize(s)) == canonicalize(s)` -- verified for all
  sixteen training artifacts and for hand-written whitespace/comment
  variants in the test suite. Raises the same errors as `parse_task` on
  malformed source.

- **`evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool`**
  -- parses `source` and evaluates it against `trace` as described
  above, per-construct. Always returns a plain `bool`.

Also exported for introspection/testing: the exception classes
(`WarehouseDSLError`, `WarehouseSyntaxError`, `WarehouseValidationError`)
and the AST node classes (`Label`, `AnyOf`, `Visit`, `Avoid`, `Order`,
`Within`, `AvoidUntil`, `Every`, `And`, `Or`).

## Files

- `warehouse_dsl/core.py` -- lexer, recursive-descent parser, canonical
  formatter, and finite-trace interpreter (stdlib only: `re`,
  `dataclasses`, `typing`).
- `warehouse_dsl/__init__.py` -- re-exports the public API.
- `training_artifacts/train_01.wdsl` ... `train_16.wdsl` -- one source
  per training card, independently authored in this language.
- `tests/test_warehouse_dsl.py` -- parser/validation/canonicalization/
  evaluation unit tests, plus one round-trip check per training
  artifact.

## Compliance notes

- No raw LTL formula appears anywhere in the grammar or the source
  files; every construct name and parameter is a task-domain notion
  (visit, avoid, ordering, a bounded deadline, avoid-until, a
  universally-quantified trigger, and/or) defined directly in terms of
  step indices and label membership.
- No `eval`, `exec`, dynamic `import`, or reflection of any kind appears
  in `core.py`'s treatment of task source; the only stdlib imports used
  by the package itself are `re`, `dataclasses`, and `typing`, for
  tokenizing and typing the interpreter -- task source is never passed
  to any of Python's own code-execution primitives.
- There is no arbitrary Python callback hook and no general escape
  hatch: the eight requirement constructs and two target forms above are
  the entire language, the keyword set is closed and checked explicitly
  against a fixed set, and any other identifier in requirement or target
  position is a parse error.
