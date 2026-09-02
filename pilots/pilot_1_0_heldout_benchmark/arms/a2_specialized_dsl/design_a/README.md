# Specialized task DSL — design A

Design seed: `1101`.

This is a closed, compositional DSL for acceptance of finite warehouse traces.
It covers the task concepts present in the training catalog without exposing
temporal-logic syntax, Python callbacks, `eval`, imports, attribute access, or
other executable escape hatches.

## Public API

```python
from solution import canonicalize_task, encode_task, evaluate_task, parse_task

accepted = evaluate_task(source, trace)
task = parse_task(source)
canonical_source = canonicalize_task(source)
source_from_neutral_ir = encode_task(neutral_task_spec)
```

`trace` is any finite sequence whose steps expose a `propositions` set and a
`resource(name)` integer accessor, as warehouse `TraceStep` objects do.

`encode_task(TaskSpec)` is the deterministic authoring bridge from the supplied
Neutral IR. It copies the closed node tree into the DSL AST and formats it. No
information is hidden outside the returned source: the task ID, requirement
IDs and order, node nesting, option order, symbols, numeric bounds, and
comparison operators are all explicit. `parse_task(encode_task(spec))` is the
parser round trip into the immutable DSL AST.

## Grammar

Strings are JSON double-quoted strings. Integers are decimal. Whitespace and
`#` line comments are ignored.

```text
task        := "task" string "{" requirement+ "}"
requirement := "require" string "=" expression ";"

expression := "visit"          "(" string ")"
            | "avoid"          "(" string ")"
            | "ordered_visit"  "(" string ("," string)* ")"
            | "deadline"       "(" string "," integer "," integer ")"
            | "maintain_until" "(" string "," string ")"
            | "on"             "(" string "," expression ")"
            | "alternative"    "(" expression ("," expression)* ")"
            | "all_of"         "(" expression ("," expression)* ")"
            | "count_at_most"  "(" string "," integer ")"
            | "once"           "(" string ")"
            | "since"          "(" string "," string ")"
            | "threshold"      "(" string "," comparison "," integer ")"
            | "priority"       "(" expression ("," expression)* ")"

comparison := "<" | "<=" | "==" | ">=" | ">"
```

Argument roles are deliberately positional and fixed:

- `deadline(event, lower, upper)` uses inclusive offsets from the current
  evaluation point and requires `0 <= lower <= upper`.
- `maintain_until(forbidden, goal)` requires a future goal and forbids the
  named proposition strictly before its first occurrence. The goal step itself
  is not part of the maintained prefix.
- `on(trigger, obligation)` checks the obligation from every trigger step. It
  is true when the trigger never occurs.
- `once(event)` checks the prefix through the current step.
- `since(condition, landmark)` uses the latest landmark and includes both that
  step and the current step.
- `threshold(resource, comparison, value)` checks every remaining step.
- `priority(first, second, ...)` accepts if an option accepts; `priority_rank`
  separately returns the first successful option's zero-based rank.
- Multiple top-level `require` declarations, and members of `all_of`, are
  conjunctive. `alternative` is disjunctive. Event counts are counts of trace
  steps containing the proposition.

Ordered visits use strictly increasing step indices. Thus propositions `A` and
`B` on the same step cannot alone satisfy `ordered_visit("A", "B")`.

## Example

```text
task "pickup-and-deliver" {
  require "sequence" = ordered_visit("A", "B", "C");
  require "safe" = all_of(avoid("X"), threshold("battery", >=, 5));
  require "reaction" = on("A", deadline("B", 1, 10));
}
```

`format_task` emits one canonical representation: two-space requirement
indentation, normalized commas, JSON string escaping, source order preserved,
and a final newline. Parsing that output always reconstructs the same immutable
AST.
