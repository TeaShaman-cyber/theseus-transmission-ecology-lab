import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from transmission_ecology.graph import adjacency_matrix, cycle_rank_beta1, load_graph


BASE = {
    "schema_version": 1,
    "graph_id": "shared-v0",
    "nodes": ["n1", "n2", "n3", "n4"],
    "edges": [
        {"source": "n1", "target": "n2", "weight": 1.0},
        {"source": "n2", "target": "n3", "weight": 1.0},
        {"source": "n3", "target": "n1", "weight": 1.0},
        {"source": "n3", "target": "n4", "weight": 1.0},
        {"source": "n4", "target": "n1", "weight": 1.0},
    ],
}


class GraphTests(unittest.TestCase):
    def load(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_graph(path)

    def test_shared_graph_has_expected_beta1_and_orientation(self):
        graph = self.load(BASE)
        self.assertEqual(cycle_rank_beta1(graph), 2)
        A = adjacency_matrix(graph)
        self.assertEqual(A.shape, (4, 4))
        self.assertEqual(A[1, 0], 1.0)  # n1 -> n2 means target row, source column
        self.assertEqual(A[0, 1], 0.0)

    def test_duplicate_nodes_fail_closed(self):
        payload = dict(BASE, nodes=["n1", "n1"])
        with self.assertRaisesRegex(ValueError, "duplicate node"):
            self.load(payload)

    def test_dangling_edge_fails_closed(self):
        payload = dict(BASE, edges=[{"source": "n1", "target": "missing", "weight": 1.0}])
        with self.assertRaisesRegex(ValueError, "unknown node"):
            self.load(payload)

    def test_nonpositive_or_nonfinite_weights_fail_closed(self):
        for weight in (0.0, -1.0, math.nan, math.inf):
            with self.subTest(weight=weight):
                payload = dict(BASE, edges=[{"source": "n1", "target": "n2", "weight": weight}])
                with self.assertRaises(ValueError):
                    self.load(payload)


if __name__ == "__main__":
    unittest.main()
