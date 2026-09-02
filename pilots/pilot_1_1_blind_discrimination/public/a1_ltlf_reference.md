# Fixed A1 language: standard finite-trace LTL

Return exactly one formula using only:

```text
atomic propositions
!  &  |  ->  X  F  G  U
parentheses
```

Warehouse labels are written as atoms `at_A`, `at_B`, `at_C`, `at_D`, and
`at_X`. For example, “eventually visit A” is `F at_A`.

`X` is strong next: `X p` is false at the final trace position. `F` and `G`
include the current position. Until is strong: `p U q` requires a future or
current position satisfying `q`, with `p` at every earlier position.

There is no bounded operator. Expand an inclusive future window `[l,u]` as:

```text
X^l p | X^(l+1) p | ... | X^u p
```

Write powers by nesting `X`. For example, 1–3 steps is:

```text
X at_B | X X at_B | X X X at_B
```

Use parentheses whenever scope might be unclear. Do not use macros, custom
operators, comments, code fences, or prose in the submitted artifact.

