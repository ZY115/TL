"""Training-suite semantic gate for the frozen A1 and A2 arms."""

from __future__ import annotations

from collections.abc import Callable

from arms.a1_ltlf.compiler import compile_task
from arms.a1_ltlf.monitor import compile_ltlf
from arms.a2_specialized_dsl import design_a, design_b, design_c
from environments.warehouse import TraceStep, Warehouse
from experiments.p0_calibration import validation_traces
from neutral_ir.interpreter import evaluate_ir
from neutral_ir.schema import TaskSpec

ParsedEvaluator = Callable[[tuple[TraceStep, ...]], bool]


def arm_evaluators(task: TaskSpec) -> dict[str, ParsedEvaluator]:
    """Compile or parse each authored task once, before evaluating traces."""

    a1_dfa = compile_ltlf(compile_task(task))

    source_a = design_a.encode_task(task)
    parsed_a = design_a.parse_task(source_a)

    source_b = design_b.encode_task(task)
    parsed_b = design_b.parse_task(source_b)

    source_c = design_c.encode_task(task)
    parsed_c = design_c.parse_task(source_c)

    return {
        "A1_LTLf": a1_dfa.accepts,
        "A2a_DSL": lambda trace: design_a.evaluate(parsed_a, trace),
        "A2b_DSL": lambda trace: all(
            design_b.requirement_diagnostics(parsed_b, trace).values()
        ),
        "A2c_DSL": lambda trace: all(
            design_c.requirement_diagnostics(parsed_c, trace).values()
        ),
    }


def conformance_rows(
    task: TaskSpec, warehouse: Warehouse, *, seed: int
) -> list[dict[str, object]]:
    evaluators = arm_evaluators(task)
    categories = (
        "uniform_random",
        "constructive_satisfying",
        "targeted_mutation",
    )
    counters = {
        (arm, category): {"matches": 0, "mismatches": 0}
        for arm in evaluators
        for category in categories
    }
    for category, trace in validation_traces(warehouse, seed=seed):
        expected = evaluate_ir(task, trace)
        for arm, evaluate in evaluators.items():
            observed = evaluate(trace)
            field = "matches" if observed == expected else "mismatches"
            counters[arm, category][field] += 1
    return [
        {
            "task_id": task.id,
            "arm": arm,
            "trace_type": category,
            "num_trajectories": values["matches"] + values["mismatches"],
            "oracle_matches": values["matches"],
            "oracle_mismatches": values["mismatches"],
            "random_seed": seed,
        }
        for (arm, category), values in counters.items()
    ]
