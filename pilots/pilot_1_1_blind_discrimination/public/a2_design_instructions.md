# Blind specialized-DSL design assignment

Design one reasonable closed language for authoring the warehouse tasks in the
provided natural-language training cards. You may infer useful abstractions
from those examples. You are not given a benchmark ontology or any future audit
task.

## Required public API

Provide a Python package exposing:

```python
parse_task(source: str)
canonicalize(source: str) -> str
evaluate_task(source: str, trace: tuple[frozenset[str], ...]) -> bool
```

The source returned by an author must contain all task-specific information.
Do not hide event names, bounds, branch choices, or nesting in uncounted files.

Also provide one independently authored source under `training_artifacts/` for
each supplied training task card. These examples will be checked against a
private semantic oracle before the language is frozen.

## Design freedom

You may use task-domain constructs, nested combinators, an FSM-like notation,
a schema, helpers, a deterministic parser/formatter, and a reusable
interpreter. A compositional language is welcome if the training examples lead
you to it. Do not intentionally make the language weak or verbose.

The language must not contain raw LTL formulas, arbitrary Python callbacks,
`eval`, `exec`, arbitrary imports from task source, a general-purpose escape
hatch, or a serialization of any external IR. Unknown constructs must be
rejected.

Write a README defining every construct directly in finite-trace terms. The
trace conventions are fixed by `warehouse.md`.

## Isolation

Use only the files copied into this design bundle and your assigned empty
output directory. Do not inspect the surrounding repository, other designs,
hidden tests, future tasks, Pilot 1.0, or coordinator files. Record the supplied
design seed tag in the README. The tag distinguishes independent design
sessions; it is not a benchmark parameter.

