import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from transmission_ecology.research_qa import _source_currentness, build_current_receipt, evaluate_research_contract


ROOT = Path(__file__).resolve().parents[1]

BASE_CONTRACT = {
    "schema_version": 1,
    "experiment_id": "deterministic-v0",
    "question": "Which declared invariants survive substrate change?",
    "hypothesis": "Selected operator-level invariants remain comparable across substrates.",
    "falsifiers": ["shared metrics add no value beyond domain-specific baselines"],
    "declared_metrics": ["spectral_radius", "cycle_rank_beta1"],
    "required_controls": ["subcritical", "supercritical", "topology_only"],
    "limitations": ["linear deterministic model only"],
    "independent_witness": {"required": True, "kind": "spectral_or_hodge"},
    "receipt_contract": {"schema_version": 2, "float_significant_digits": 12},
}


def run_receipt(commit: str, *, all_passed: bool = True, schema_version: int = 2, digits: int = 12):
    return {
        "schema_version": schema_version,
        "numeric_policy": {"float_significant_digits": digits},
        "source_commit": commit,
        "controls": {"all_passed": all_passed},
    }


class ResearchQATests(unittest.TestCase):
    def test_missing_run_receipts_is_unknown_not_pass(self):
        out = evaluate_research_contract(BASE_CONTRACT, {}, None, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "UNKNOWN")
        self.assertEqual(out["authority"], "NONE")

    def test_missing_required_witness_is_unknown_not_pass(self):
        runs = {name: run_receipt("a" * 40) for name in ("virus", "meme", "agent")}
        out = evaluate_research_contract(BASE_CONTRACT, runs, None, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "UNKNOWN")

    def test_commit_mismatch_fails_closed(self):
        runs = {name: run_receipt("b" * 40) for name in ("virus", "meme", "agent")}
        witness = {"source_commit": "a" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "FAIL")

    def test_receipt_numeric_policy_mismatch_fails_closed(self):
        runs = {
            "virus": run_receipt("a" * 40),
            "meme": run_receipt("a" * 40, digits=10),
            "agent": run_receipt("a" * 40),
        }
        witness = {"source_commit": "a" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "receipt_contract_mismatch")

    def test_complete_contract_can_pass_without_claiming_truth(self):
        runs = {name: run_receipt("a" * 40) for name in ("virus", "meme", "agent")}
        witness = {"source_commit": "a" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "PASS")
        self.assertEqual(out["authority"], "NONE")
        self.assertNotIn("scientific_truth", out)

    def test_dirty_experiment_surface_is_stale_even_when_source_equals_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            (root / "pyproject.toml").write_text("version = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "pyproject.toml"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            (root / "pyproject.toml").write_text("version = 2\n", encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_experiment_surface_dirty")

    def test_current_repository_reports_truthful_lifecycle_state(self):
        payload = build_current_receipt(ROOT)
        self.assertIn(
            payload["source_currentness"],
            {"CURRENT", "BOUND_UNCHANGED_SURFACE", "STALE"},
        )
        if payload["source_currentness"] == "CURRENT":
            self.assertEqual(payload["source_commit"], payload["storage_head"])
            self.assertEqual(payload["contract_status"], "PASS")
        elif payload["source_currentness"] == "BOUND_UNCHANGED_SURFACE":
            self.assertNotEqual(payload["source_commit"], payload["storage_head"])
            self.assertEqual(payload["contract_status"], "PASS")
        else:
            self.assertEqual(payload["contract_status"], "UNKNOWN")

    def test_degraded_witness_cannot_pass(self):
        runs = {name: run_receipt("a" * 40) for name in ("virus", "meme", "agent")}
        witness = {"source_commit": "a" * 40, "status": "DEGRADED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "DEGRADED")
        self.assertEqual(out["authority"], "NONE")

    def test_witness_commit_mismatch_fails_closed(self):
        runs = {name: run_receipt("a" * 40) for name in ("virus", "meme", "agent")}
        witness = {"source_commit": "b" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_commit_mismatch")

    def test_endpoint_exit_code_matches_reported_contract_state(self):
        check = ROOT / "tools" / "research" / "check"
        self.assertTrue(check.is_file())
        self.assertTrue(check.stat().st_mode & 0o111)
        expected = build_current_receipt(ROOT)
        result = subprocess.run(
            [str(check)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        expected_rc = 0 if expected["contract_status"] == "PASS" else 1 if expected["contract_status"] == "FAIL" else 2
        self.assertEqual(result.returncode, expected_rc, result.stdout + result.stderr)
        self.assertEqual(payload["contract_status"], expected["contract_status"])
        self.assertEqual(payload["authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
