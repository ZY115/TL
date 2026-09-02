# Fixed A3 monitor API

Return one Python source file defining:

```python
class Monitor:
    def reset(self) -> None:
        ...

    def step(self, propositions: set[str]) -> None:
        ...

    def finish(self) -> bool:
        ...
```

The harness constructs one monitor, calls `reset()`, calls `step()` once per
finite trace position in order, and finally calls `finish()`.

Use ordinary Python data structures and helper methods when useful. Do not
import repository code, read files, use network access, call `eval`/`exec`, or
emit anything except the source artifact. The monitor must decide the task
from the proposition sets it receives; no hidden configuration is supplied.

