"""Independent automaton and environment-product reference pipeline."""

from .automaton import DFA, SynthesisBudgetExceeded, compile_reference_automaton

__all__ = ["DFA", "SynthesisBudgetExceeded", "compile_reference_automaton"]
