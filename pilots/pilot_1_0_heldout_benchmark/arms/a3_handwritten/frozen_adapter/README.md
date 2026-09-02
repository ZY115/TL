# Frozen A3 adapter

This adapter was frozen before analysis cases were opened. It reads Python
source only and never receives the Neutral IR or the natural-language task.
It extracts API shape, public state variables, literal counter bounds, optional
requirement-region annotations, and an optional `abstract_state()` interface.

Without a source-derived finite abstraction it returns `approximate_only`;
malformed or non-API artifacts return `extraction_failed`. Even an
`adapter_exact_candidate` must pass transition-closure validation before being
reported as exact. This intentionally allows extraction failure and prevents a
bespoke post-hoc adapter from silently re-specifying each task.
