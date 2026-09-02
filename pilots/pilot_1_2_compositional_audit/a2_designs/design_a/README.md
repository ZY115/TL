# Warehouse DSL

A closed, compositional domain-specific language for authoring warehouse
trace requirements: pickup, inspection, delivery, charging, and hazard
avoidance. Implemented as a self-contained Python package (standard library
only -- no `eval`, no `exec`, no dynamic imports from task source, no
serialization of an external formula language, no escape hatch).

Design seed tag: **11101** (from `design_seed_tag.txt`; this tag identifies
the design session and is not a language parameter).

## Public API

```python
from warehouse_dsl import parse_task, canonicalize, evaluate_task

parse_task(source: str)                                     # -> immutable tree
canonicalize(source: str) -> str                             # deterministic, idempotent
evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool
```

* `parse_task` raises `warehouse_dsl.WarehouseSyntaxError` (a `ValueError`
  subclass) on any malformed source: unknown keywords, wrong arity,
  malformed numeric bounds, malformed label sets, unbalanced brackets, or
  trailing input after a complete requirement. Every construct not defined
  in the grammar below -- including any raw temporal-logic formula, Python
  expression, or foreign syntax -- is rejected this way.
* `canonicalize` parses and re-prints in a fixed normal form: sorted label
  sets, fixed spacing, no comments. It is a pure function of the parsed
  tree, so it is deterministic and idempotent.
* `evaluate_task` parses `source` and evaluates the resulting tree against
  `trace`, starting at the current step `cur = 0`. It always returns a
  plain `bool`; a trace that ends before some visit, order, deadline, or
  until-goal can be completed simply evaluates to `False` (only malformed
  *source* raises).

## Trace model (fixed by `warehouse.md`)

A trace is a finite ordered sequence of steps, indexed from 0. Each step is
a set of proposition labels; a label is true at a step exactly when it
appears in that step's set. All semantics below are defined purely in terms
of finite index arithmetic over the trace -- there are no infinite traces,
no fairness assumptions, and no hidden state.

Every construct is defined relative to a **current step** `cur`. At the top
level, `evaluate_task` begins evaluation with `cur = 0`. Inside `every`, the
body is (re-)evaluated once per trigger occurrence with `cur` set to that
occurrence's index -- this is what `warehouse.md` calls "evaluation begins
at the trigger step." A `within(...)` clause with a `then` follow-on
evaluates its follow-on with `cur` set to whichever in-window step was
chosen as the witness. `all_of` and `any_of` pass the same `cur` they
received straight through to each part.

## Grammar

```
requirement  ::= "visit" "(" labelset ")"
               | "avoid" "(" labelset ")"
               | "avoid_until" "(" labelset "," labelset ")"
               | "order" "(" labelset ("," labelset)+ ")"
               | "within" "(" number "," number "," labelset ")" ("then" requirement)?
               | "every" "(" labelset "," requirement ")"
               | "all_of" "(" requirement ("," requirement)+ ")"
               | "any_of" "(" requirement ("," requirement)+ ")"

labelset     ::= label | "{" label ("," label)* "}"
label        ::= uppercase letter, then letters/digits/underscore
number       ::= one or more digits (non-negative integer)
```

Whitespace (including newlines) is insignificant between tokens. `#` starts
a comment that runs to end of line. A source file is exactly one
`requirement`; trailing tokens after it are a parse error. Label sets
reject duplicate labels (e.g. `{A, A}`) as malformed. `order`, `all_of`, and
`any_of` each require at least two comma-separated operands. `within`
requires two non-negative integer bounds with `hi >= lo`. The keyword
`then` is only valid immediately after a complete `within(...)` clause.
Any lowercase word that is not one of the eight keywords above is rejected
as an unknown construct, and any uppercase-leading identifier is *only*
ever accepted where a label is grammatically expected -- there is no way to
smuggle in an arbitrary formula, callback, or foreign syntax.

## Constructs, defined in finite-trace terms

Let `N = len(trace)`, and let `cur` be the current step at which a node is
evaluated (0 at the top level; see above for how nested constructs shift
it). `L(j)` denotes the label set at step `j` (`trace[j]`).

### `visit(labelset)`
Holds iff there exists `j` with `cur <= j < N` and `L(j) & labelset` is
non-empty. "Reach one of these labels at the current step or later" --
inclusive of the current step. At the top level (`cur = 0`) this is
"visit at least once, anywhere in the trace." Nested as an `every(...)`
body ("after A, reach ..."), the current step is the trigger step, and
the contract's general nesting rule -- "evaluation begins at the trigger
step" -- makes that step count: a label co-occurring with the trigger
already satisfies `visit`. `visit` is the language's only unbounded
reachability construct; see "Worked example: the trigger step counts"
below for why there is no separate exclusive-of-trigger version.

### `avoid(labelset)`
Holds iff for every `j` with `cur <= j < N`, `L(j) & labelset` is empty.
Vacuously true if `cur >= N`. At the top level this is "never visit any of
these labels, anywhere in the trace."

### `avoid_until(avoid_labelset, until_labelset)`
Let `c*` be the smallest `j` with `cur <= j < N` and `L(j) & until_labelset`
non-empty (a qualifying "C" at the current step or later). The node holds
iff `c*` exists and, for every `j` with `cur <= j < c*`, `L(j) &
avoid_labelset` is empty. `avoid_labelset` may co-occur with
`until_labelset` at `c*` itself -- it is only forbidden *strictly before*
`c*`. If no qualifying step exists at or after `cur`, the node is `False`
(an unfulfilled until-goal). Picking the earliest qualifying `C` is always
at least as easy to satisfy as any later one (a later `C` only enlarges the
forbidden window), so this single witness fully determines the truth
value -- there is no other choice of `C` that could succeed if the
earliest one fails. When nested inside `every` (or inside a `within`
follow-on), `cur` is the trigger/witness step itself, so both the search
for `C` and the start of the forbidden window begin there -- "from that
point on."

### `order(labelset_1, ..., labelset_k)` (k >= 2)
Holds iff there exist strictly increasing indices
`cur <= j_1 < j_2 < ... < j_k < N` such that `L(j_m) & labelset_m` is
non-empty for every `m`. Irrelevant steps and repeated visits anywhere in
the trace are allowed; only the existence of *some* increasing witness
sequence matters, so an early match for a later label never blocks a
later match for that same label from completing the requirement.

### `within(lo, hi, labelset)` [`then requirement`]
Holds iff there exists `j` with `cur + lo <= j <= cur + hi` and
`0 <= j < N` such that `L(j) & labelset` is non-empty, **and**, if a
`then requirement` clause is present, that follow-on requirement holds
when evaluated with the current step set to that same `j`. Both bounds are
inclusive offsets from `cur`; offset 0 is the current step itself, so a
lower bound of 1 excludes it ("N steps later, the trigger step does not
count"). When several steps in the window carry `labelset`, any one of
them may serve, and the follow-on is measured from whichever is chosen: the
node holds iff *at least one* in-window witness makes both the label test
and the follow-on succeed, so a witness whose follow-on fails does not
disqualify a different witness whose follow-on succeeds. A `within` with
no `then` clause degenerates to a plain bounded reachability check.

### `every(labelset, requirement)`
Holds iff for every index `i` with `0 <= i < N` and `L(i) & labelset`
non-empty (every occurrence of the trigger, anywhere in the trace), the
body `requirement` holds when evaluated with the current step set to `i`.
Vacuously true if the trigger never occurs. Each occurrence is checked
independently, so different occurrences may satisfy the body via different
witnesses or different branches of an inner `any_of`.

### `all_of(requirement, ..., requirement)` (>= 2 parts)
Holds iff every part holds, each evaluated at the same `cur` this node
itself received. Conjunction.

### `any_of(requirement, ..., requirement)` (>= 2 parts)
Holds iff at least one part holds, each evaluated at the same `cur` this
node itself received. Disjunction (inclusive: more than one part may hold).

## Worked example: why `avoid_until`'s forbidden window includes the trigger step

For `every(B, avoid_until(X, C))`, take the trace (indices 0..5):

```
step:   0    1    2      3    4    5
labels: {}   {}   {B,X}  {}   {}   {C}
```

`B` occurs at index 2, so the body is evaluated with `cur = 2`. The
earliest `C` at or after `cur` is at index 5, so `c* = 5`. The forbidden
window is `cur <= j < c*`, i.e. indices `2, 3, 4` -- which *includes* index
2, the trigger step itself. Since `X` is present at index 2, this trace
violates the requirement and `evaluate_task` returns `False`. This mirrors
the top-level (non-nested) case, where `cur = 0` and the forbidden window
`0 <= j < c*` likewise includes step 0: "evaluation begins at the trigger
step" means the trigger step is treated exactly like a fresh step 0 for
this sub-check, not as an exempt step that precedes the window.

## Worked example: the trigger step counts

For `every(A, visit({B, C}))`, take the trace (indices 0..4):

```
step:   0      1      2    3    4
labels: {B,D}  {A,X}  {A}  {X}  {A,B}
```

`A` occurs at indices 1, 2, and 4. The hardest occurrence is index 4, the
last step: the body is evaluated with `cur = 4`, and `visit({B, C})` asks
for `j` with `4 <= j < 5` -- the only candidate is `j = 4` itself. Step 4's
label set is `{A, B}`, which contains `B`, so the check succeeds using the
trigger step as its own witness. All three occurrences succeed the same
way (each finds a `B` at or after its own index, including index 4 finding
one *at* its own index), so `evaluate_task` returns `True`.

An earlier revision of this language instead used a construct that
searched *strictly after* the trigger step for this case, by analogy with
`within`'s "the trigger step does not count" rule. That analogy does not
hold: the contract excludes the trigger step only for `within`'s explicit
numeric offsets (an author-chosen lower bound), and separately states the
general rule for every other nested construct -- "evaluation begins at the
trigger step." Under the strictly-after reading, index 4 would have no
step left to search (`4 < j < 5` is empty) and the trace above would be
rejected, contradicting the contract. The construct was removed rather
than fixed in place, since a correctly inclusive version would have been
semantically identical to `visit`; `training_artifacts/train_06.wdsl` uses
`visit` accordingly.

## Mapping from the sixteen training cards

| Card | Source (canonical form) |
|------|--------------------------|
| train_01 | `visit(A)` |
| train_02 | `avoid(X)` |
| train_03 | `order(A, B)` |
| train_04 | `every(A, within(1, 4, B))` |
| train_05 | `avoid_until(X, C)` |
| train_06 | `every(A, visit({B, C}))` |
| train_07 | `all_of(visit(A), avoid(X))` |
| train_08 | `order(A, B, C)` |
| train_09 | `every(B, avoid_until(X, C))` |
| train_10 | `visit({B, D})` |
| train_11 | `every(A, within(1, 3, B) then visit(C))` |
| train_12 | `every(A, within(1, 2, B) then avoid_until(X, C))` |
| train_13 | `any_of(all_of(order(A, B), avoid(X)), visit(D))` |
| train_14 | `every(C, within(2, 4, D))` |
| train_15 | `all_of(order(C, D), every(C, within(1, 5, D)))` |
| train_16 | `every(A, any_of(within(1, 2, B) then visit(C), visit(D)))` |

Each `training_artifacts/train_NN.wdsl` file contains one independently
authored source in this language for the corresponding card, with a short
comment paraphrasing the card (comments carry no semantic weight -- every
event name, bound, branch choice, and nesting decision is in the code, not
the comment).

## Design notes

* **Why `visit` is separate from `within`, and why there is no second
  unbounded construct.** `within` always takes two finite numeric bounds;
  there is no "infinity" literal in the grammar, so unbounded reachability
  ("at least once", "at or after that B", "at that step or later", "after
  A, reach B or C") needs its own construct: `visit`. It was tempting to
  give `visit` an exclusive-of-trigger sibling for "afterwards" wording
  (train_06), by analogy with `within`'s documented trigger-step
  exclusion. That analogy is wrong: the contract excludes the trigger step
  only for `within`'s explicit numeric offsets, and states the opposite as
  the general nesting rule -- "evaluation begins at the trigger step."
  See "Worked example: the trigger step counts" above for the trace that
  exposed this and why the exclusive construct was removed rather than
  kept alongside `visit`.
* **Why `then` only attaches to `within`.** `warehouse.md` ties the
  follow-on rule specifically to "a bounded requirement." No training card
  attaches a follow-on to `order`, `avoid`, or a plain `visit`, so the
  grammar does not offer that option -- `then` is only recognized
  immediately after a complete `within(...)` clause.
  A `then` follow-on may itself be any `requirement`, including another
  `within ... then ...`, which lets a chain of bounded responses be
  expressed with the same single mechanism (no card needs more than one
  level, but nothing about the follow-on rule is specific to depth 1).
* **Why label sets are one uniform building block.** `visit`,
  `avoid`, `avoid_until`'s two arguments, each step of `order`, `within`'s
  target, and `every`'s trigger all accept the same `labelset` production
  (a single label, or a brace-enclosed set meaning "any of these"). This
  is the one recurring test the cards need -- "does this step carry one of
  these labels" -- reused everywhere rather than inventing separate single-
  label and multi-label grammar rules.
* **Why `avoid` and `avoid_until` are separate constructs.** `avoid` (train_02)
  is an unconditional prohibition with no eventual condition; a trace that
  never contains the label satisfies it outright.  `avoid_until` (train_05,
  train_09, train_12) additionally *requires* an eventual qualifying step.
  Collapsing them would either weaken train_02 (implicitly demanding an
  eventual "release" event that the card never mentions) or make
  `avoid_until` unable to express its required deadline -- so both are
  kept, each matching a distinct pattern actually present in the cards.
* **What was deliberately not added.** There is no general sequencing
  combinator beyond `order` (flat, unconditional strictly-increasing
  visits) and the `within ... then ...` follow-on (conditional, tied to a
  bounded witness) -- no card composes visits in a way that needs a third
  shape. There is no "exactly one of" (xor) combinator -- train_13's "both
  plans may be completed" explicitly calls for inclusive `any_of`, and no
  card ever asks for exclusivity. There is no numeric counting/aggregation
  construct (e.g. "at least N times") -- no card asks for one. Triggers,
  targets, and `order` steps only ever range over concrete labels drawn
  from the source text itself; there is no variable binding, arithmetic
  over labels, or indirection.
