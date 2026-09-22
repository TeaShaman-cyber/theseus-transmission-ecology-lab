"""Linearized cultural/meme transmission adapter.

Reconstruction is represented by a one-parent transition matrix. Repeated
exposure and complex contagion are explicitly out of scope for deterministic v0.
"""

from __future__ import annotations

from transmission_ecology.models.base import _finite_nonnegative_scalar, build_from_graph


def build_operator(graph, params):
    transmission = _finite_nonnegative_scalar(params.get("transmission_scale"), "transmission_scale")
    retention = _finite_nonnegative_scalar(params.get("attention_retention", 1.0), "attention_retention")
    return build_from_graph(graph, params, effective_scale=transmission * retention)
