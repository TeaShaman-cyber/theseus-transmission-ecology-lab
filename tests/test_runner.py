import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from transmission_ecology.cli import main, run_substrate, write_reference_set
from transmission_ecology.receipt import sha256_file
from transmission_ecology.research_qa import build_current_receipt


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

    def test_reference_receipts_match_frozen_inputs_when_research_surface_is_current(self):
        qa = build_current_receipt(ROOT)
        if qa["source_currentness"] == "STALE":
            self.assertEqual(qa["contract_status"], "UNKNOWN")
            self.assertEqual(qa["authority"], "NONE")
            return
        self.assertIn(qa["source_currentness"], {"CURRENT", "BOUND_UNCHANGED_SURFACE"})
        self.assertEqual(qa["contract_status"], "PASS")

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
        self.assertEqual(
            controls["parameters_sha256"],
            sha256_file(ROOT / "experiments" / "v0" / "controls.json"),
        )

    def test_run_v0_requires_write_reference_flag_before_persistent_write(self):
        with patch("transmission_ecology.cli.write_reference_set") as writer:
            with self.assertRaises(SystemExit):
                main(["run-v0", "--horizon", "1"])
            writer.assert_not_called()

    def test_run_v0_rejects_dirty_execution_surface_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics = root / "src" / "transmission_ecology" / "metrics.py"
            metrics.parent.mkdir(parents=True)
            metrics.write_text("VALUE = 1\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "qa@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "QA"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
            metrics.write_text("VALUE = 2\n")

            with patch("transmission_ecology.cli.Path.cwd", return_value=root):
                with patch("transmission_ecology.cli.write_reference_set", return_value={}) as writer:
                    with self.assertRaises(SystemExit):
                        main(["run-v0", "--write-reference"])
                    writer.assert_not_called()

    def test_run_v0_rejects_dirty_package_initializer_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "src" / "transmission_ecology"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "qa@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "QA"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
            (package / "__init__.py").write_text("VALUE = 2\n")

            with patch("transmission_ecology.cli.Path.cwd", return_value=root):
                with patch("transmission_ecology.cli.write_reference_set", return_value={}) as writer:
                    with self.assertRaises(SystemExit):
                        main(["run-v0", "--write-reference"])
                    writer.assert_not_called()

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
