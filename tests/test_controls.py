import json
import unittest
from pathlib import Path

from transmission_ecology.cli import run_controls
from transmission_ecology.graph import load_graph


ROOT = Path(__file__).resolve().parents[1]


class ControlsTests(unittest.TestCase):
    def test_same_graph_crosses_threshold_only_by_parameterization(self):
        graph_path = ROOT / "experiments" / "v0" / "shared-graph.json"
        controls_path = ROOT / "experiments" / "v0" / "controls.json"
        graph = load_graph(graph_path)
        controls = json.loads(controls_path.read_text(encoding="utf-8"))
        receipt = run_controls(graph, graph_path, controls, controls_path, source_commit="b" * 40)
        self.assertTrue(receipt["all_passed"])
        self.assertLess(receipt["checks"]["subcritical"]["spectral_radius"], 1.0)
        self.assertGreater(receipt["checks"]["supercritical"]["spectral_radius"], 1.0)
        self.assertLess(receipt["checks"]["subcritical"]["final_mass"], receipt["checks"]["subcritical"]["initial_mass"])
        self.assertGreater(receipt["checks"]["supercritical"]["final_mass"], receipt["checks"]["supercritical"]["initial_mass"])
        topology = receipt["checks"]["topology_only"]
        self.assertEqual(topology["cycle_rank_beta1"], 2)
        self.assertEqual(
            topology["subcritical_graph_sha256"],
            topology["supercritical_graph_sha256"],
        )
        self.assertEqual(topology["graph_sha256"], topology["subcritical_graph_sha256"])
        self.assertEqual(topology["subcritical_regime"], "decay")
        self.assertEqual(topology["supercritical_regime"], "growth")
        self.assertTrue(topology["same_topology"])
        self.assertTrue(topology["opposite_regimes"])
        self.assertTrue(topology["topology_only_explanation_rejected"])


if __name__ == "__main__":
    unittest.main()
