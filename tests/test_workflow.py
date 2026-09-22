import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def test_canonical_qa_fetches_full_history_for_provenance_checks(self):
        path = ROOT / ".github" / "workflows" / "qa.yml"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@v4", text)
        self.assertIn("fetch-depth: 0", text)

    def test_v0_replay_uses_exact_execution_commit_and_research_receipt(self):
        path = ROOT / ".github" / "workflows" / "v0-replay.yml"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("pull_request:", text)
        self.assertIn("paths:", text)
        self.assertIn("receipts/research-qa/**", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("source_commit", text)
        self.assertIn("git worktree add --detach", text)
        self.assertIn("tools/run-v0", text)
        self.assertIn("diff -ru", text)
        self.assertIn("tools/research/check --output receipts/research-qa/v0.json", text)
        self.assertIn("python-version: '3.11.16'", text)
        self.assertIn("actions/upload-artifact@v4", text)


if __name__ == "__main__":
    unittest.main()
