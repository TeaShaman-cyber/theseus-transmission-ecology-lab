import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DevCheckTests(unittest.TestCase):
    def test_dev_check_exists_is_executable_and_has_terminal_pass_marker(self):
        check = ROOT / "tools" / "dev" / "check"
        self.assertTrue(check.is_file())
        self.assertTrue(check.stat().st_mode & 0o111)
        text = check.read_text(encoding="utf-8")
        self.assertIn("DEV_CHECK_PASS", text)

    @unittest.skipIf(os.environ.get("THESEUS_TRANSMISSION_DEV_CHECK_RUNNING") == "1", "avoid recursive endpoint self-test")
    def test_dev_check_passes_on_clean_repo(self):
        result = subprocess.run(
            [str(ROOT / "tools" / "dev" / "check")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DEV_CHECK_PASS", result.stdout)
