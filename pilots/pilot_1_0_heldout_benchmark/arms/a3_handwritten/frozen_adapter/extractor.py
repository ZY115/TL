"""Source-only structural extraction; never consults task IR or natural language."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    status: str
    state_variables: tuple[str, ...]
    integer_bounds: tuple[int, ...]
    requirement_regions: tuple[str, ...]
    provenance_total: bool
    human_supplied_facts: tuple[str, ...]
    reason: str


def extract_source_model(source: str) -> ExtractionResult:
    """Admissible adapter: every returned fact is syntactically source-derived."""

    try:
        module = ast.parse(source)
    except SyntaxError as error:
        return ExtractionResult(
            "extraction_failed", (), (), (), False, (), f"syntax error: {error}"
        )
    state_variables: set[str] = set()
    integer_bounds: set[int] = set()
    requirement_regions: set[str] = set()
    has_api = {"reset": False, "step": False, "finish": False}
    has_abstract_state = False
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef):
            if node.name in has_api:
                has_api[node.name] = True
            if node.name == "abstract_state":
                has_abstract_state = True
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "self" and not node.attr.startswith("_"):
                state_variables.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            integer_bounds.add(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "REQUIREMENT_REGIONS":
                    try:
                        value = ast.literal_eval(node.value)
                        if isinstance(value, dict):
                            requirement_regions.update(map(str, value))
                    except (ValueError, TypeError):
                        pass
    if not all(has_api.values()):
        return ExtractionResult(
            "extraction_failed",
            tuple(sorted(state_variables)),
            tuple(sorted(integer_bounds)),
            tuple(sorted(requirement_regions)),
            False,
            (),
            "Monitor API methods are incomplete",
        )
    facts = []
    if integer_bounds:
        facts.append("counter_bounds_inferred_from_literals")
    if requirement_regions:
        facts.append("requirement_annotations_present_in_source")
    if has_abstract_state:
        facts.append("state_abstraction_method_present_in_source")
    status = "adapter_exact_candidate" if has_abstract_state else "approximate_only"
    return ExtractionResult(
        status,
        tuple(sorted(state_variables)),
        tuple(sorted(integer_bounds)),
        tuple(sorted(requirement_regions)),
        bool(requirement_regions),
        tuple(facts),
        (
            "Exactness still requires transition-closure validation."
            if has_abstract_state
            else "No finite abstract-state interface was derivable from source alone."
        ),
    )
