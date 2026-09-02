# Warehouse Task Language, design B

Design seed tag: **2202**.

WTL is a small, closed language for writing finite warehouse-trace tasks. It
is deliberately phrased in task concepts rather than raw temporal logic. The
parser recognizes only the constructs below: there is no `eval`, callback,
import, user-defined function, or executable extension point.

## Source form

```text
task "delivery" {
  require "route": ordered("A", "B", "C");
  require "safety": all_of(avoid("X"), threshold("battery", >=, 5));
  require "reaction": on("A", deadline("B", 1, 10));
}
```

Strings use JSON quoting and escapes. Integers are decimal. Whitespace is
insignificant. Every requirement ends in `;`, identifiers are unique within a
task, and all constructs have fixed arity except the explicitly variadic
constructs.

| Construct | Meaning from the current evaluation position |
| --- | --- |
| `visit(event)` | the event occurs at least once |
| `avoid(event)` | the event never occurs |
| `ordered(e1, ...)` | events occur in the listed order, at distinct indices |
| `deadline(event, lower, upper)` | event occurs at an inclusive relative index |
| `maintain_until(forbidden, goal)` | a goal occurs and forbidden is absent before its first occurrence |
| `on(trigger, obligation)` | obligation holds from every trigger occurrence |
| `alternative(expr, ...)` | at least one option holds |
| `all_of(expr, ...)` | every nested requirement holds |
| `count_at_most(event, maximum)` | suffix occurrence count does not exceed maximum |
| `once(event)` | event occurred at or before the current position |
| `since(condition, landmark)` | a landmark occurred and condition held from its latest occurrence through now |
| `threshold(resource, op, value)` | comparison holds at every remaining step; `op` is `<`, `<=`, `==`, `>=`, or `>` |
| `priority(expr, ...)` | Boolean acceptance is any successful option; `priority_rank` retains the first successful rank |

Multiple top-level requirements are conjoined. `on` with no trigger occurrence
is satisfied. A `deadline` bound is relative to each evaluation position, so it
also works as a nested trigger obligation. Trace positions include the initial
warehouse state at index zero.

## API

```python
from arms.a2_specialized_dsl.design_b import (
    encode_task,
    evaluate_task,
    format_task,
    parse_task,
)

task = parse_task(source)
canonical_source = format_task(task)
accepted = evaluate_task(canonical_source, trace)

# Deterministic authoring bridge from neutral_ir.schema.TaskSpec:
source = encode_task(neutral_task)
assert format_task(parse_task(source)) == source
```

`parse_task` consumes exactly one task and rejects trailing text. `format_task`
is canonical: parsing and formatting it again produces identical bytes.
`requirement_diagnostics` exposes per-requirement Boolean results without
altering the all-requirements acceptance rule.

`encode_task(TaskSpec)` maps every Neutral IR node to its matching WTL
construct. It preserves the task ID, requirement IDs and order, nested
structure, event/resource strings, numeric bounds, comparison operator, and
alternative/priority order in the returned source. The returned source is the
complete authored task; the bridge carries no hidden side data.

## Validation

From the benchmark root, run:

```bash
python -m unittest arms.a2_specialized_dsl.design_b.test_design_b
```
