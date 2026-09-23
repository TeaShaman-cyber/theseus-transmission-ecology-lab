"""Linearized viral transmission adapter.

Mutation is represented by a one-parent variant transition matrix. Coinfection
and reassortment are explicitly out of scope for deterministic v0.
"""

from __future__ import annotations

from transmission_ecology.models.base import _finite_nonnegative_scalar, build_from_graph


def build_operator(graph, params):
    transmission = _finite_nonnegative_scalar(params.get("transmission_scale"), "transmission_scale")
    loss = _finite_nonnegative_scalar(params.get("recovery_loss", 0.0), "recovery_loss")
    if loss > 1.0:
        raise ValueError("recovery_loss must be <= 1")
    return build_from_graph(graph, params, effective_scale=transmission * (1.0 - loss))
