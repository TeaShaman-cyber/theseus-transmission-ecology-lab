"""Linearized AI-agent / engineering-invariant transfer adapter.

Local adaptation is represented by a one-parent transition matrix and evaluator
weights. Multi-artifact composition is explicitly out of scope for deterministic v0.
"""

from __future__ import annotations

from transmission_ecology.models.base import _finite_nonnegative_scalar, build_from_graph, validate_variants


def build_operator(graph, params):
    transmission = _finite_nonnegative_scalar(params.get("transmission_scale"), "transmission_scale")
    variants = validate_variants(params)
    fitness = params.get("evaluator_weights")
    if not isinstance(fitness, list) or len(fitness) != len(variants):
        raise ValueError("evaluator_weights must match variants")
    return build_from_graph(
        graph,
        params,
        effective_scale=transmission,
        variant_fitness=fitness,
    )
