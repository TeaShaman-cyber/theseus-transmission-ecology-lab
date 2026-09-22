import json
import tempfile
import unittest
from pathlib import Path

from transmission_ecology.receipt import build_run_receipt, canonical_json_bytes, sha256_file, write_json_atomic


class ReceiptTests(unittest.TestCase):
    def test_canonical_serialization_is_byte_identical(self):
        payload = {"b": [2, 1], "a": {"z": 0.5}}
        self.assertEqual(canonical_json_bytes(payload), canonical_json_bytes(payload))
        self.assertEqual(canonical_json_bytes(payload), b'{"a":{"z":0.5},"b":[2,1]}\n')

    def test_run_receipt_binds_provenance_and_has_no_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {}
            for name in ("contract", "graph", "params"):
                path = root / f"{name}.json"
                path.write_text(json.dumps({"name": name}), encoding="utf-8")
                paths[name] = path
            receipt = build_run_receipt(
                experiment_id="deterministic-v0",
                source_commit="a" * 40,
                substrate="virus",
                horizon=8,
                contract_path=paths["contract"],
                graph_path=paths["graph"],
                parameters_path=paths["params"],
                metrics={"spectral_radius": 0.8},
                controls={"all_passed": True},
            )
            self.assertEqual(receipt["source_commit"], "a" * 40)
            self.assertEqual(receipt["scientific_authority"], "NONE")
            self.assertEqual(receipt["contract_sha256"], sha256_file(paths["contract"]))
            self.assertEqual(receipt["graph_sha256"], sha256_file(paths["graph"]))
            self.assertEqual(receipt["parameters_sha256"], sha256_file(paths["params"]))

    def test_atomic_writer_round_trips_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            payload = {"z": 1, "a": 2}
            write_json_atomic(path, payload)
            self.assertEqual(path.read_bytes(), canonical_json_bytes(payload))


if __name__ == "__main__":
    unittest.main()
