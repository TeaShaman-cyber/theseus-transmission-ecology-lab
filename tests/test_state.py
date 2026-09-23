import unittest

import numpy as np

from transmission_ecology.state import simulate, validate_operator


class StateTests(unittest.TestCase):
    def test_simulate_linear_operator(self):
        K = np.array([[0.0, 0.5], [0.5, 0.0]])
        x0 = np.array([1.0, 0.0])
        states = simulate(K, x0, horizon=2)
        np.testing.assert_allclose(states[-1], np.array([0.25, 0.0]))

    def test_operator_shape_must_match_state_size(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            validate_operator(np.ones((2, 3)), state_size=2)
        with self.assertRaisesRegex(ValueError, "shape"):
            validate_operator(np.eye(3), state_size=2)

    def test_operator_entries_must_be_finite_and_nonnegative(self):
        cases = [
            np.array([[1.0, -0.1], [0.0, 1.0]]),
            np.array([[1.0, np.nan], [0.0, 1.0]]),
            np.array([[1.0, np.inf], [0.0, 1.0]]),
        ]
        for K in cases:
            with self.subTest(K=K):
                with self.assertRaises(ValueError):
                    validate_operator(K, state_size=2)

    def test_initial_state_must_be_finite_nonnegative_and_match_operator(self):
        for x0 in (np.array([-1.0, 0.0]), np.array([np.nan, 0.0]), np.array([1.0])):
            with self.subTest(x0=x0):
                with self.assertRaises(ValueError):
                    simulate(np.eye(2), x0, horizon=1)

    def test_horizon_must_be_nonnegative_integer(self):
        for horizon in (-1, 1.5, True):
            with self.subTest(horizon=horizon):
                with self.assertRaises(ValueError):
                    simulate(np.eye(2), np.array([1.0, 0.0]), horizon=horizon)


if __name__ == "__main__":
    unittest.main()
