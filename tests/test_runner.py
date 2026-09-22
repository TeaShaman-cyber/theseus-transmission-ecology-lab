import json
import tempfile
import unittest
from pathlib import Path

from transmission_ecology.cli import run_substrate, write_reference_set
from transmission_ecology.receipt import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def test_run_substrate_emits_common_receipt_contract(self):
        graph = ROOT / "experiments" / "v0" / "shared-graph.json"
        params = ROOT / "experiments" / "v0" / "parameters" / "virus.json"
        receipt = run_substrate(
            "virus", graph, params, horizon=8, source_commit="c" * 40
        )
        self.assertEqual(receipt["substrate"], "virus")
        self.assertEqual(receipt["source_commit"], "c" * 40)
        self.assertEqual(receipt["scientific_authority"], "NONE")
        self.assertEqual(receipt["graph_sha256"], sha256_file(graph))
        self.assertEqual(receipt["parameters_sha256"], sha256_file(params))
        self.assertIn("spectral_radius", receipt["metrics"])
        self.assertIn("variant_shannon_entropy", receipt["metrics"])

    def test_committed_reference_receipts_bind_current_frozen_inputs(self):
        contract = ROOT / "experiments" / "v0" / "contract.json"
        graph = ROOT / "experiments" / "v0" / "shared-graph.json"
        expected_contract = sha256_file(contract)
        expected_graph = sha256_file(graph)
        for name in ("virus", "meme", "agent"):
            receipt = json.loads((ROOT / "receipts" / "reference" / f"v0-{name}.json").read_text())
            params = ROOT / "experiments" / "v0" / "parameters" / f"{name}.json"
            self.assertEqual(receipt["contract_sha256"], expected_contract)
            self.assertEqual(receipt["graph_sha256"], expected_graph)
            self.assertEqual(receipt["parameters_sha256"], sha256_file(params))
        controls = json.loads((ROOT / "receipts" / "reference" / "v0-controls.json").read_text())
        self.assertEqual(controls["graph_sha256"], expected_graph)
        self.assertEqual(controls["parameters_sha256"], sha256_file(ROOT / "experiments" / "v0" / "controls.json"))

    def test_reference_set_is_byte_deterministic_for_same_source_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = write_reference_set(ROOT, out, horizon=8, source_commit="d" * 40)
            bytes_a = {p.name: p.read_bytes() for p in sorted(out.glob("*.json"))}
            second = write_reference_set(ROOT, out, horizon=8, source_commit="d" * 40)
            bytes_b = {p.name: p.read_bytes() for p in sorted(out.glob("*.json"))}
            self.assertEqual(first.keys(), second.keys())
            self.assertEqual(bytes_a, bytes_b)
            self.assertEqual(set(bytes_a), {"v0-virus.json", "v0-meme.json", "v0-agent.json", "v0-controls.json"})


if __name__ == "__main__":
    unittest.main()
