import math
import unittest

import numpy as np

from transmission_ecology.metrics import (
    dominant_variant_share,
    perturbation_recovery_ratio,
    spectral_radius,
    summarize_run,
    surviving_variant_count,
    time_to_extinction_or_horizon,
    variant_shannon_entropy,
)


class MetricsTests(unittest.TestCase):
    def test_spectral_radius_uses_eigenvalue_magnitude(self):
        self.assertAlmostEqual(spectral_radius(np.diag([0.5, 1.25])), 1.25)
        self.assertAlmostEqual(spectral_radius(np.array([[0.0, -2.0], [0.5, 0.0]])), 1.0)

    def test_zero_mass_diversity_metrics_are_zero(self):
        state = np.zeros(4)
        self.assertEqual(variant_shannon_entropy(state, node_count=2, variant_count=2), 0.0)
        self.assertEqual(dominant_variant_share(state, node_count=2, variant_count=2), 0.0)
        self.assertEqual(surviving_variant_count(state, 2, 2), 0)

    def test_variant_metrics_aggregate_across_nodes(self):
        state = np.array([1.0, 0.0, 0.5, 0.5])  # node-major: [n0v0,n0v1,n1v0,n1v1]
        self.assertEqual(surviving_variant_count(state, 2, 2), 2)
        self.assertAlmostEqual(dominant_variant_share(state, 2, 2), 0.75)
        expected = -(0.75 * math.log(0.75) + 0.25 * math.log(0.25))
        self.assertAlmostEqual(variant_shannon_entropy(state, 2, 2), expected)

    def test_perturbation_recovery_ratio_is_bounded(self):
        baseline = np.array([2.0, 1.0])
        perturbed = np.array([1.0, 0.5])
        self.assertAlmostEqual(perturbation_recovery_ratio(baseline, perturbed), 0.5)
        self.assertEqual(perturbation_recovery_ratio(np.zeros(2), np.ones(2)), 0.0)
        self.assertEqual(perturbation_recovery_ratio(np.ones(2), np.ones(2) * 2), 1.0)

    def test_extinction_time_returns_first_zero_mass_step_or_horizon(self):
        states = [np.array([1.0]), np.array([0.1]), np.array([0.0]), np.array([0.0])]
        self.assertEqual(time_to_extinction_or_horizon(states), 2)
        self.assertEqual(time_to_extinction_or_horizon(states[:2]), 1)

    def test_summarize_run_emits_common_metric_names(self):
        states = [np.array([1.0, 0.0]), np.array([0.5, 0.5])]
        summary = summarize_run(
            np.eye(2),
            states,
            node_count=1,
            variant_count=2,
            cycle_rank_beta1_value=0,
            perturbed_final=np.array([0.25, 0.25]),
        )
        self.assertEqual(
            set(summary),
            {
                "spectral_radius",
                "subcritical_or_supercritical",
                "cycle_rank_beta1",
                "total_mass_by_step",
                "variant_shannon_entropy",
                "surviving_variant_count",
                "dominant_variant_share",
                "time_to_extinction_or_horizon",
                "perturbation_recovery_ratio",
            },
        )

    def test_nonfinite_or_shape_mismatch_fails_closed(self):
        with self.assertRaises(ValueError):
            spectral_radius(np.array([[1.0, np.nan], [0.0, 1.0]]))
        with self.assertRaises(ValueError):
            variant_shannon_entropy(np.ones(3), node_count=2, variant_count=2)
        with self.assertRaises(ValueError):
            perturbation_recovery_ratio(np.array([1.0]), np.array([np.inf]))


if __name__ == "__main__":
    unittest.main()
