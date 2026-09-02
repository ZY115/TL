"""Fixed author-facing API for free-form handwritten monitors."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Monitor(ABC):
    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def step(self, propositions: set[str], resources: dict[str, int]) -> None: ...

    @abstractmethod
    def finish(self) -> bool: ...
