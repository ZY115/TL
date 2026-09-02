# RouteTask DSL — specialized design C

Design seed tag: `3303`.

RouteTask is a small, closed language for finite warehouse missions. Its surface
constructs describe route-domain intent rather than exposing temporal-logic
syntax or a general programming language. A source file contains one named task
and one or more named requirements:

```text
task "pickup_delivery" {
  require "route": route("A", "B", "C");
  require "safety": all_of(never("X"), maintain_resource("battery", ">=", 5));
  require "response": after_each("A", reach_between("B", 1, 10));
}
```

The parser accepts insignificant whitespace. `format_task` and `canonicalize`
emit one deterministic spelling: two-space requirement indentation, JSON string
escaping, fixed punctuation spacing, input requirement order, and a final
newline. Task and requirement IDs must be non-empty and requirement IDs must be
unique.

## Closed expression vocabulary

| Form | Finite-trace meaning from the current evaluation position |
|---|---|
| `reach(event)` | The event occurs now or later. |
| `never(event)` | The event does not occur now or later. |
| `route(e1, e2, ...)` | The events occur in the listed order at strictly increasing trace indices. |
| `reach_between(event, lower, upper)` | The event occurs at an inclusive relative index in `[lower, upper]`. |
| `avoid_until(forbidden, goal)` | A goal is eventually reached and the forbidden event is absent strictly before the first goal. |
| `after_each(trigger, obligation)` | The nested obligation holds from every position carrying the trigger. It is vacuously true if no trigger occurs. |
| `any_of(e1, e2, ...)` | At least one nested expression holds. |
| `all_of(e1, e2, ...)` | Every nested expression holds. |
| `visits_at_most(event, maximum)` | The number of event-labelled trace steps is no greater than the non-negative maximum. |
| `seen(event)` | The event occurred at or before the current position. This is especially useful inside `after_each`. |
| `condition_since(condition, landmark)` | A landmark has occurred, and the condition holds continuously from its latest occurrence through the current position. |
| `maintain_resource(resource, comparison, value)` | Every remaining resource value passes one of `<`, `<=`, `==`, `>=`, `>`. |
| `prefer(e1, e2, ...)` | Boolean acceptance succeeds when any option succeeds; `preference_rank` returns the first successful option's zero-based rank. |

`route` requires at least one event. `any_of`, `all_of`, and `prefer` require at
least two nested expressions. Bounds and visit maxima are validated when parsed.
Every top-level requirement must pass for `evaluate_task` to return true.

## API and trace shape

The primary API is:

```python
evaluate_task(source: str, trace) -> bool
```

`parse_task`, `format_task`, `canonicalize`, `evaluate_expression`,
`requirement_diagnostics`, and `preference_rank` are also reusable. For benchmark
authoring, `encode_task(neutral_task)` converts a complete
`neutral_ir.schema.TaskSpec` into canonical DSL source, and
`decode_task(source)` reconstructs the neutral task. Consequently,
`decode_task(encode_task(task)) == task` for every supported, valid task: no
structure or parameter is hidden outside the counted source. A trace step may be
a warehouse `TraceStep` (with `.propositions` and `.resource(name)`) or a mapping
such as:

```python
{"propositions": ["A", "SAFE"], "resources": {"battery": 12, "load": 1}}
```

The source grammar only recognizes the forms in the table, JSON strings, base-10
integers, and fixed task punctuation. Unknown calls, surplus arguments, comments,
attribute access, imports, callbacks, and host-language expressions are rejected;
the implementation contains no `eval` or executable extension point.

Run the focused dependency-free test suite from the benchmark root with:

```sh
python -m unittest arms.a2_specialized_dsl.design_c.test_task_dsl
```
