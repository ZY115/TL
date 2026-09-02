# Warehouse trace contract

A trace is a finite ordered sequence of steps. Each step exposes a set of
proposition labels, such as `A`, `B`, `C`, `D`, or `X`. A label is true at a
step exactly when it appears in that step's set.

The first recorded step is index 0. “Within 4 steps after A” includes offsets
1, 2, 3, and 4 after each occurrence of `A`; it does not include the trigger
step. A requested lower and upper bound are both inclusive.

“Visit A and later B” requires strictly increasing indices. Irrelevant steps
and repeated visits are allowed. An early `B` does not prevent a later `B`
from completing the ordered requirement.

“After A, ...” applies to every step containing `A`. If no `A` occurs, that
triggered requirement is vacuously satisfied unless the task separately
requires a visit to A.

“Avoid X until C” requires a `C` at the current or a later step and forbids X
strictly before the selected C. X is allowed on the C endpoint. When nested
after a trigger, evaluation begins at the trigger step.

A bounded requirement may carry a follow-on: “reach B within 1–3 steps and
then …” means some step in that window carries `B` **and** the follow-on holds
with evaluation beginning at that same B step. If several B steps fall in the
window, any one of them may serve, but the follow-on is measured from the one
chosen. “At or after that B” therefore includes the B step itself.

All final answers are Boolean. An unfinished finite trace is rejected whenever
the task still requires an unfulfilled visit, order, deadline, or until-goal.

