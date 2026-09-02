# Fixed A1 language: standard finite-trace LTL

Return exactly one formula using only:

```text
atomic propositions
!  &  |  ->  X  F  G  U
parentheses
```

Warehouse labels are written as atoms `at_A`, `at_B`, `at_C`, `at_D`, and
`at_X`. For example, "eventually visit A" is `F at_A`.

`X` is strong next: `X p` is false at the final trace position. `F` and `G`
include the current position. Until is strong: `p U q` requires a current or
future position satisfying `q`, with `p` at every earlier position.

There is no bounded operator and no exponent notation. Write "within one to
three steps after the current position" by nesting `X` once per step and
joining the alternatives with `|`:

```text
X at_B | X X at_B | X X X at_B
```

Two to four steps is:

```text
X X at_B | X X X at_B | X X X X at_B
```

Any formula may appear inside `X`, `F`, `G`, or `U`, or beside an atom with
`&`. For example, "B two steps from now, and from that step C is eventually
reached" is `X X (at_B & F at_C)`.

Use parentheses whenever scope might be unclear. Do not use macros, custom
operators, the `^` character, comments, code fences, or prose in the
submitted artifact.
