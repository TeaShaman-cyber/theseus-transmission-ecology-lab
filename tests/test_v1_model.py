import unittest

import numpy as np

from experiments.v1.model import (
    two_stage_kron_operator,
    two_stage_step,
    two_stage_variant_operator,
)


class V1ModelTests(unittest.TestCase):
    def setUp(self):
        self.x0 = np.array([0.0, 1.0])
        self.V = np.array([[0.95, 0.08], [0.05, 0.92]])
        self.I = np.eye(2)
        self.W = np.diag([1.0, 0.95])

    def test_reviewed_abc_fixture(self):
        cases = {
            "target-only": (self.I, self.W, [0.0, 1.0], [0.08, 0.92], [0.08, 0.874]),
            "source-only": (self.W, self.I, [0.0, 0.95], [0.076, 0.874], [0.076, 0.874]),
            "two-stage": (self.W, self.W, [0.0, 0.95], [0.076, 0.874], [0.076, 0.8303]),
        }
        for name, (source, target, source_ready, adapted, persistent) in cases.items():
            with self.subTest(name=name):
                out = two_stage_step(self.x0, self.V, source, target)
                np.testing.assert_allclose(out["source_ready"], source_ready, rtol=0.0, atol=1e-12)
                np.testing.assert_allclose(out["adapted"], adapted, rtol=0.0, atol=1e-12)
                np.testing.assert_allclose(out["persistent"], persistent, rtol=0.0, atol=1e-12)
                np.testing.assert_array_equal(out["next_state"], out["persistent"])

    def test_composed_and_global_operators(self):
        B = two_stage_variant_operator(self.V, self.W, self.W)
        np.testing.assert_allclose(B, self.W @ self.V @ self.W, rtol=0.0, atol=1e-12)
        A = np.array([[0.0, 1.0], [1.0, 0.0]])
        K = two_stage_kron_operator(A, self.V, self.W, self.W, scale=0.5)
        np.testing.assert_allclose(K, np.kron(A, B) * 0.5, rtol=0.0, atol=1e-12)

    def test_invalid_domains_fail_closed(self):
        dense_gate = np.array([[1.0, 0.1], [0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, "diagonal"):
            two_stage_variant_operator(self.V, dense_gate, self.I)
        sub_stochastic = np.array([[0.8, 0.0], [0.0, 0.8]])
        with self.assertRaisesRegex(ValueError, "columns"):
            two_stage_variant_operator(sub_stochastic, self.I, self.I)

    def test_complex_inputs_fail_closed_before_float_cast(self):
        complex_transition = np.array([[1.0 + 1.0j, 0.0], [0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, "real-valued"):
            two_stage_variant_operator(complex_transition, self.I, self.I)

        complex_gate = np.array([[1.0 + 1.0j, 0.0], [0.0, 1.0]])
        with self.assertRaisesRegex(ValueError, "real-valued"):
            two_stage_variant_operator(self.V, complex_gate, self.I)

        with self.assertRaisesRegex(ValueError, "real-valued"):
            two_stage_step(np.array([0.0, 1.0 + 1.0j]), self.V, self.I, self.I)

        complex_adjacency = np.array([[0.0, 1.0 + 1.0j], [1.0, 0.0]])
        with self.assertRaisesRegex(ValueError, "real-valued"):
            two_stage_kron_operator(complex_adjacency, self.V, self.I, self.I, scale=1.0)


if __name__ == "__main__":
    unittest.main()
