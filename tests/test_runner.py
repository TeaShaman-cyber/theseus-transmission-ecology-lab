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

    def test_labeled_graph_node_order_does_not_change_scientific_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            graph_payload = json.loads(
                (ROOT / "experiments" / "v0" / "shared-graph.json").read_text()
            )
            controls_payload = json.loads(
                (ROOT / "experiments" / "v0" / "controls.json").read_text()
            )
            controls_payload["run_seed_node"] = "n1"

            receipts = []
            for label, nodes in (
                ("a", list(graph_payload["nodes"])),
                ("b", ["n4", "n2", "n3", "n1"]),
            ):
                root = tmp_root / label
                exp = root / "experiments" / "v0"
                params_dir = exp / "parameters"
                params_dir.mkdir(parents=True)
                graph = dict(graph_payload)
                graph["nodes"] = nodes
                (exp / "shared-graph.json").write_text(json.dumps(graph))
                (exp / "controls.json").write_text(json.dumps(controls_payload))
                (exp / "contract.json").write_text(
                    (ROOT / "experiments" / "v0" / "contract.json").read_text()
                )
                witness_dir = exp / "witness"
                witness_dir.mkdir()
                (witness_dir / "wolfram-v0.wl").write_text(
                    (ROOT / "experiments" / "v0" / "witness" / "wolfram-v0.wl").read_text()
                )
                for name in ("virus", "meme", "agent"):
                    (params_dir / f"{name}.json").write_text(
                        (ROOT / "experiments" / "v0" / "parameters" / f"{name}.json").read_text()
                    )
                out = root / "receipts" / "reference"
                write_reference_set(root, out, horizon=8, source_commit="d" * 40)
                receipts.append(json.loads((out / "v0-virus.json").read_text()))

            first, second = (item["metrics"] for item in receipts)
            self.assertEqual(
                first["subcritical_or_supercritical"],
                second["subcritical_or_supercritical"],
            )
            self.assertEqual(first["cycle_rank_beta1"], second["cycle_rank_beta1"])
            self.assertEqual(
                first["surviving_variant_count"], second["surviving_variant_count"]
            )
            self.assertEqual(
                first["time_to_extinction_or_horizon"],
                second["time_to_extinction_or_horizon"],
            )
            for left, right in zip(
                first["total_mass_by_step"], second["total_mass_by_step"]
            ):
                self.assertAlmostEqual(left, right, places=12)
            for key in (
                "spectral_radius",
                "variant_shannon_entropy",
                "dominant_variant_share",
                "perturbation_recovery_ratio",
            ):
                self.assertAlmostEqual(first[key], second[key], places=12)

    def test_named_variant_order_does_not_change_scientific_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            graph_text = (ROOT / "experiments" / "v0" / "shared-graph.json").read_text()
            contract_text = (ROOT / "experiments" / "v0" / "contract.json").read_text()
            controls_payload = json.loads(
                (ROOT / "experiments" / "v0" / "controls.json").read_text()
            )
            controls_payload["run_seed_node"] = "n1"
            controls_payload["run_seed_variants"] = {
                "virus": "v0",
                "meme": "m0",
                "agent": "a0",
            }
            base_virus = json.loads(
                (ROOT / "experiments" / "v0" / "parameters" / "virus.json").read_text()
            )

            receipts = []
            for label, mutate in (("a", False), ("b", True)):
                root = tmp_root / label
                exp = root / "experiments" / "v0"
                params_dir = exp / "parameters"
                params_dir.mkdir(parents=True)
                (exp / "shared-graph.json").write_text(graph_text)
                (exp / "controls.json").write_text(json.dumps(controls_payload))
                (exp / "contract.json").write_text(contract_text)
                witness_dir = exp / "witness"
                witness_dir.mkdir()
                (witness_dir / "wolfram-v0.wl").write_text(
                    (ROOT / "experiments" / "v0" / "witness" / "wolfram-v0.wl").read_text()
                )
                for name in ("meme", "agent"):
                    (params_dir / f"{name}.json").write_text(
                        (ROOT / "experiments" / "v0" / "parameters" / f"{name}.json").read_text()
                    )
                virus = json.loads(json.dumps(base_virus))
                if mutate:
                    virus["variants"] = list(reversed(virus["variants"]))
                    matrix = virus["variant_transition"]
                    virus["variant_transition"] = [
                        [matrix[1][1], matrix[1][0]],
                        [matrix[0][1], matrix[0][0]],
                    ]
                (params_dir / "virus.json").write_text(json.dumps(virus))
                out = root / "receipts" / "reference"
                write_reference_set(root, out, horizon=8, source_commit="d" * 40)
                receipts.append(json.loads((out / "v0-virus.json").read_text()))

            first, second = (item["metrics"] for item in receipts)
            for key in (
                "spectral_radius",
                "variant_shannon_entropy",
                "dominant_variant_share",
                "perturbation_recovery_ratio",
            ):
                self.assertAlmostEqual(first[key], second[key], places=12)
            for left, right in zip(
                first["total_mass_by_step"], second["total_mass_by_step"]
            ):
                self.assertAlmostEqual(left, right, places=12)

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
