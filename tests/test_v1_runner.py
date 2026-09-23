import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from experiments.v1.run import _display_output_path, build_canonical_receipt

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


    def test_durable_write_refuses_untracked_python_shadow_module(self):
        shadow = ROOT / "sitecustomize.py"
        self.assertFalse(shadow.exists())
        shadow.write_text("SHADOW = True\n", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "receipt.json"
                result = subprocess.run(
                    [str(ROOT / "tools" / "run-v1"), "--output", str(out)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("dirty v1 execution surface", result.stderr)
        finally:
            shadow.unlink(missing_ok=True)

    def test_absolute_output_outside_repo_reports_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "receipt.json"
            self.assertEqual(_display_output_path(out, ROOT), str(out))

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
