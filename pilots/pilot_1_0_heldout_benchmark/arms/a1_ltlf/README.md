# A1 frozen finite-trace stack

This stack is frozen from the 15 training tasks. It provides Core finite-trace
operators plus explicit training-time extensions for counting, past-time,
numeric resources, and ranked alternatives. Strong `X` is false at the final
position. A deadline expands to `X^l p | ... | X^u p`.

`Priority` is not claimed to be an LTLf trace operator. Boolean acceptance is
the disjunction of ranked options; the source preserves their order for a
separate preference result. The prefix-DFA compiler enforces the Pilot 1.0
1,000,000-state and 60-second budgets and reports budget exhaustion rather than
dropping the case.

No held-out-specific macro is defined here.
