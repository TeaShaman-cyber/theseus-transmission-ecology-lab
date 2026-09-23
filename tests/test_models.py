import json
import unittest
from pathlib import Path

import numpy as np

from transmission_ecology.graph import adjacency_matrix, load_graph
from transmission_ecology.models import agent, meme, virus
from transmission_ecology.models.base import (
    kron_operator,
    two_stage_kron_operator,
    two_stage_step,
    two_stage_variant_operator,
)


ROOT = Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = load_graph(ROOT / "experiments" / "v0" / "shared-graph.json")
        cls.A = adjacency_matrix(cls.graph)

    def load_params(self, name):
        return json.loads((ROOT / "experiments" / "v0" / "parameters" / f"{name}.json").read_text())

    def test_each_adapter_has_same_shape_and_graph_support(self):
        adapters = {"virus": virus, "meme": meme, "agent": agent}
        for name, module in adapters.items():
            with self.subTest(name=name):
                K = module.build_operator(self.graph, self.load_params(name))
                self.assertEqual(K.shape, (8, 8))
                self.assertTrue(np.all(np.isfinite(K)))
                self.assertTrue(np.all(K >= 0))
                for target in range(4):
                    for source in range(4):
                        block = K[target * 2:(target + 1) * 2, source * 2:(source + 1) * 2]
                        self.assertEqual(bool(np.any(block > 0)), bool(self.A[target, source] > 0))

    def test_transition_columns_must_sum_to_one(self):
        V = np.array([[0.8, 0.1], [0.1, 0.8]])
        with self.assertRaisesRegex(ValueError, "columns"):
            kron_operator(self.A, V, scale=1.0)

    def test_negative_or_nonfinite_fitness_fails_closed(self):
        V = np.eye(2)
        for fitness in ([1.0, -0.1], [1.0, np.inf]):
            with self.subTest(fitness=fitness):
                with self.assertRaises(ValueError):
                    kron_operator(self.A, V, scale=1.0, variant_fitness=fitness)

    def test_v1_two_stage_fixture_matches_reviewed_oracle(self):
        x0 = np.array([0.0, 1.0])
        V = np.array([[0.95, 0.08], [0.05, 0.92]])
        I = np.eye(2)
        W = np.diag([1.0, 0.95])
        cases = {
            "target-only": (I, W, [0.0, 1.0], [0.08, 0.92], [0.08, 0.874]),
            "source-only": (W, I, [0.0, 0.95], [0.076, 0.874], [0.076, 0.874]),
            "two-stage": (W, W, [0.0, 0.95], [0.076, 0.874], [0.076, 0.8303]),
        }
        for name, (W_source, W_target, source_ready, adapted, persistent) in cases.items():
            with self.subTest(name=name):
                out = two_stage_step(x0, V, W_source, W_target)
                np.testing.assert_allclose(out["source_ready"], source_ready, rtol=0.0, atol=1e-12)
                np.testing.assert_allclose(out["adapted"], adapted, rtol=0.0, atol=1e-12)
                np.testing.assert_allclose(out["persistent"], persistent, rtol=0.0, atol=1e-12)
                np.testing.assert_array_equal(out["next_state"], out["persistent"])

    def test_v1_two_stage_operator_matches_stage_composition(self):
        V = np.array([[0.95, 0.08], [0.05, 0.92]])
        W = np.diag([1.0, 0.95])
        B = two_stage_variant_operator(V, W, W)
        np.testing.assert_allclose(B, W @ V @ W, rtol=0.0, atol=1e-12)
        K = two_stage_kron_operator(self.A, V, W, W, scale=0.5)
        np.testing.assert_allclose(K, np.kron(self.A, B) * 0.5, rtol=0.0, atol=1e-12)

    def test_v1_two_stage_rejects_invalid_stage_domains(self):
        valid_v = np.eye(2)
        dense_gate = np.array([[1.0, 0.1], [0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, "diagonal"):
            two_stage_variant_operator(valid_v, dense_gate, np.eye(2))
        sub_stochastic = np.array([[0.8, 0.0], [0.0, 0.8]])
        with self.assertRaisesRegex(ValueError, "columns"):
            two_stage_variant_operator(sub_stochastic, np.eye(2), np.eye(2))

    def test_substrate_boundaries_are_explicit_in_module_docs(self):
        self.assertIn("reassortment", (virus.__doc__ or "").lower())
        self.assertIn("complex contagion", (meme.__doc__ or "").lower())
        self.assertIn("multi-artifact", (agent.__doc__ or "").lower())


if __name__ == "__main__":
    unittest.main()
