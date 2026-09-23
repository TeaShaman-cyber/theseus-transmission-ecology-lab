import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from experiments.v1.run import build_canonical_receipt

ROOT = Path(__file__).resolve().parents[1]


class V1RunnerTests(unittest.TestCase):
    def test_canonical_receipt_has_three_passing_cases(self):
        payload = build_canonical_receipt(ROOT)
        self.assertEqual(set(payload["cases"]), {"target-only", "source-only", "two-stage"})
        self.assertEqual(payload["scientific_authority"], "NONE")
        self.assertIsNone(payload["scientific_disposition"])
        for case in payload["cases"].values():
            self.assertEqual(case["verdict"]["stage_attribution"], "PASS", case)
            self.assertEqual(
                set(case["identity_controls"]),
                set(case["receipt"]["claimed_stages"]),
            )

    def test_cli_stdout_is_deterministic_json(self):
        result = subprocess.run(
            [str(ROOT / "tools" / "run-v1")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["fixture_id"], "canonical-v1-a1")
        self.assertEqual(payload["cases"]["two-stage"]["verdict"]["stage_attribution"], "PASS")


if __name__ == "__main__":
    unittest.main()
