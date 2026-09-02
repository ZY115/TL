"""Analysis adapter for the frozen Pilot 1.2 DSL design C.

Design C is a closed language with a top-level ``and(...)`` whose children
are the author's requirements, so requirement-level provenance is available
syntactically. This adapter maps its AST onto the coordinator gold IR and
then onto standard LTLf, which puts every exact question in
``ltlf_dfa`` within reach.

The adapter is admissible only if it agrees with the design's own
interpreter; ``tests/test_adapter.py`` checks that on the Pilot 1.2
conformance corpus for every source analysed. Its cost — this file — is
what "adapter_exact" charges A2 for: a compiler the language did not ship
with. Designs A and B would need adapters of their own; none was built.
"""

from __future__ import annotations

from itertools import product

from .. import paths
from ..blackbox import design_c
from a1_ltlf.language import Formula
from coordinator_private.oracle import schema as ir
from coordinator_private.oracle.ltlf_gold import compile_expression


PILOT_1_2 = paths.PILOT_1_2  # the frozen design lives there


def _labels(target) -> tuple[str, ...]:
    module = design_c()
    if isinstance(target, module.Label):
        return (target.name,)
    if isinstance(target, module.AnyOf):
        return tuple(target.labels)
    raise TypeError(type(target))


def _any(items: list[ir.Expression]) -> ir.Expression:
    return items[0] if len(items) == 1 else ir.AnyOf(tuple(items))


def _all(items: list[ir.Expression]) -> ir.Expression:
    return items[0] if len(items) == 1 else ir.AllOf(tuple(items))


def to_ir(node) -> ir.Expression:
    m = design_c()
    if isinstance(node, m.Visit):
        return _any([ir.Visit(l) for l in _labels(node.target)])
    if isinstance(node, m.Avoid):
        return _all([ir.Avoid(l) for l in _labels(node.target)])
    if isinstance(node, m.Order):
        choices = [_labels(t) for t in node.targets]
        return _any([ir.Ordered(tuple(seq)) for seq in product(*choices)])
    if isinstance(node, m.Within):
        then = to_ir(node.then) if node.then is not None else None
        items = [
            ir.WithinThen(l, node.lo, node.hi, then) if then is not None
            else ir.Within(l, node.lo, node.hi)
            for l in _labels(node.target)
        ]
        return _any(items)
    if isinstance(node, m.AvoidUntil):
        avoid = _labels(node.avoid_target)
        reach = _labels(node.reach_target)
        # "no forbidden label strictly before the first reach" — a conjunction
        # over forbidden labels inside a disjunction over reach labels.
        return _any([_all([ir.SafeUntil(a, r) for a in avoid]) for r in reach])
    if isinstance(node, m.Every):
        body = to_ir(node.body)
        return _all([ir.Triggered(t, body) for t in _labels(node.trigger)])
    if isinstance(node, m.And):
        return ir.AllOf(tuple(to_ir(c) for c in node.children))
    if isinstance(node, m.Or):
        return ir.AnyOf(tuple(to_ir(c) for c in node.children))
    raise TypeError(type(node))


def requirements(source: str) -> list[ir.Expression]:
    """Top-level requirement units: the children of a root ``and``."""
    m = design_c()
    tree = m.parse_task(source)
    if isinstance(tree, m.And):
        return [to_ir(c) for c in tree.children]
    return [to_ir(tree)]


def to_ltlf(source: str) -> Formula:
    return compile_expression(to_ir(design_c().parse_task(source)))


def requirement_formulas(source: str) -> list[Formula]:
    return [compile_expression(r) for r in requirements(source)]
