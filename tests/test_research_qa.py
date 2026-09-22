import json
import subprocess
import unittest
from pathlib import Path

from transmission_ecology.research_qa import build_current_receipt, evaluate_research_contract


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
}


class ResearchQATests(unittest.TestCase):
    def test_missing_run_receipts_is_unknown_not_pass(self):
        out = evaluate_research_contract(BASE_CONTRACT, {}, None, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "UNKNOWN")
        self.assertEqual(out["authority"], "NONE")

    def test_missing_required_witness_is_unknown_not_pass(self):
        runs = {
            "virus": {"source_commit": "a" * 40, "controls": {"all_passed": True}},
            "meme": {"source_commit": "a" * 40, "controls": {"all_passed": True}},
            "agent": {"source_commit": "a" * 40, "controls": {"all_passed": True}},
        }
        out = evaluate_research_contract(BASE_CONTRACT, runs, None, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "UNKNOWN")

    def test_commit_mismatch_fails_closed(self):
        runs = {
            name: {"source_commit": "b" * 40, "controls": {"all_passed": True}}
            for name in ("virus", "meme", "agent")
        }
        witness = {"source_commit": "a" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "FAIL")

    def test_complete_contract_can_pass_without_claiming_truth(self):
        runs = {
            name: {"source_commit": "a" * 40, "controls": {"all_passed": True}}
            for name in ("virus", "meme", "agent")
        }
        witness = {"source_commit": "a" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "PASS")
        self.assertEqual(out["authority"], "NONE")
        self.assertNotIn("scientific_truth", out)

    def test_stored_reference_receipts_bind_unchanged_execution_surface(self):
        payload = build_current_receipt(ROOT)
        self.assertEqual(payload["source_currentness"], "BOUND_UNCHANGED_SURFACE")
        self.assertNotEqual(payload["source_commit"], payload["storage_head"])
        self.assertEqual(payload["source_commit"], "ba251bc9238242dbab9e392e3d5b6c7cf2a5de64")

    def test_degraded_witness_cannot_pass(self):
        runs = {
            name: {"source_commit": "a" * 40, "controls": {"all_passed": True}}
            for name in ("virus", "meme", "agent")
        }
        witness = {"source_commit": "a" * 40, "status": "DEGRADED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "DEGRADED")
        self.assertEqual(out["authority"], "NONE")

    def test_witness_commit_mismatch_fails_closed(self):
        runs = {
            name: {"source_commit": "a" * 40, "controls": {"all_passed": True}}
            for name in ("virus", "meme", "agent")
        }
        witness = {"source_commit": "b" * 40, "status": "VERIFIED"}
        out = evaluate_research_contract(BASE_CONTRACT, runs, witness, source_commit="a" * 40)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_commit_mismatch")

    def test_verified_independent_witness_allows_contract_pass(self):
        payload = build_current_receipt(ROOT)
        self.assertEqual(payload["contract_status"], "PASS")
        self.assertEqual(payload["authority"], "NONE")
        self.assertEqual(payload["scientific_disposition"], "UNKNOWN_WITHIN_CURRENT_CONTRACT")
        self.assertEqual(payload["source_commit"], "ba251bc9238242dbab9e392e3d5b6c7cf2a5de64")

    def test_endpoint_is_executable_and_reports_verified_contract_state(self):
        check = ROOT / "tools" / "research" / "check"
        self.assertTrue(check.is_file())
        self.assertTrue(check.stat().st_mode & 0o111)
        result = subprocess.run([str(check)], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["contract_status"], "PASS")
        self.assertEqual(payload["authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
