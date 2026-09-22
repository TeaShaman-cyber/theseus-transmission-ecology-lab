import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from transmission_ecology.research_qa import (
    _source_currentness,
    build_current_receipt,
    evaluate_research_contract,
)


ROOT = Path(__file__).resolve().parents[1]
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40

BASE_CONTRACT = {
    "schema_version": 1,
    "experiment_id": "deterministic-v0",
    "question": "Which declared invariants survive substrate change?",
    "hypothesis": "Selected operator-level invariants remain comparable across substrates.",
    "falsifiers": ["shared metrics add no value beyond domain-specific baselines"],
    "declared_metrics": ["spectral_radius", "cycle_rank_beta1"],
    "required_controls": ["subcritical", "supercritical", "topology_only"],
    "limitations": ["linear deterministic model only"],
    "independent_witness": {
        "required": True,
        "kind": "spectral_or_hodge",
        "expected_inputs": {
            "graph_sha256": "graph-ok",
            "controls_sha256": "controls-ok",
        },
        "required_checks": {
            "cycle_rank_beta1": 2,
            "hodge1_nullity": 2,
            "subcritical_below_one": True,
            "supercritical_above_one": True,
        },
    },
    "receipt_contract": {
        "schema_version": 2,
        "float_significant_digits": 12,
    },
}

BASE_BINDINGS = {
    "runs": {
        "virus": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "virus-params-ok",
        },
        "meme": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "meme-params-ok",
        },
        "agent": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "agent-params-ok",
        },
    },
    "control": {
        "graph_sha256": "graph-ok",
        "parameters_sha256": "controls-ok",
    },
}


def run_receipt(
    name: str,
    commit: str = COMMIT_A,
    *,
    all_passed: bool = True,
    schema_version: int = 2,
    digits: int = 12,
):
    binding = BASE_BINDINGS["runs"][name]
    return {
        "schema_version": schema_version,
        "numeric_policy": {"float_significant_digits": digits},
        "experiment_id": "deterministic-v0",
        "source_commit": commit,
        "substrate": name,
        "contract_sha256": binding["contract_sha256"],
        "graph_sha256": binding["graph_sha256"],
        "parameters_sha256": binding["parameters_sha256"],
        "scientific_authority": "NONE",
        "metrics": {
            "spectral_radius": 0.8,
            "cycle_rank_beta1": 2,
        },
        "controls": {
            "all_passed": all_passed,
            "control_receipt": "v0-controls.json",
        },
    }


def valid_runs(commit: str = COMMIT_A):
    return {
        name: run_receipt(name, commit)
        for name in ("virus", "meme", "agent")
    }


def valid_control_receipt(commit: str = COMMIT_A):
    return {
        "schema_version": 2,
        "numeric_policy": {"float_significant_digits": 12},
        "experiment_id": "deterministic-v0",
        "source_commit": commit,
        "graph_sha256": "graph-ok",
        "parameters_sha256": "controls-ok",
        "scientific_authority": "NONE",
        "all_passed": True,
        "checks": {
            "subcritical": {"spectral_radius": 0.8},
            "supercritical": {"spectral_radius": 1.2},
            "topology_only": {"same_graph": True},
        },
    }


def valid_witness(commit: str = COMMIT_A):
    return {
        "experiment_id": "deterministic-v0",
        "source_commit": commit,
        "status": "VERIFIED",
        "authority": "NONE",
        "kind": "spectral_or_hodge",
        "inputs": {
            "graph_sha256": "graph-ok",
            "controls_sha256": "controls-ok",
        },
        "checks": {
            "cycle_rank_beta1": 2,
            "hodge1_nullity": 2,
            "subcritical_below_one": True,
            "supercritical_above_one": True,
        },
    }


def evaluate(runs=None, control=None, witness=None, *, source_commit=COMMIT_A, bindings=BASE_BINDINGS):
    return evaluate_research_contract(
        BASE_CONTRACT,
        valid_runs(source_commit) if runs is None else runs,
        valid_control_receipt(source_commit) if control is None else control,
        valid_witness(source_commit) if witness is None else witness,
        source_commit=source_commit,
        evidence_bindings=bindings,
    )


class ResearchQATests(unittest.TestCase):
    def test_missing_run_receipts_is_unknown_not_pass(self):
        out = evaluate_research_contract(
            BASE_CONTRACT,
            {},
            valid_control_receipt(),
            None,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "UNKNOWN")
        self.assertEqual(out["authority"], "NONE")

    def test_missing_required_witness_is_unknown_not_pass(self):
        out = evaluate(witness=None)
        self.assertEqual(out["contract_status"], "PASS")
        out = evaluate_research_contract(
            BASE_CONTRACT,
            valid_runs(),
            valid_control_receipt(),
            None,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "UNKNOWN")

    def test_commit_mismatch_fails_closed(self):
        runs = valid_runs(COMMIT_B)
        out = evaluate_research_contract(
            BASE_CONTRACT,
            runs,
            valid_control_receipt(COMMIT_A),
            valid_witness(COMMIT_A),
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL")

    def test_receipt_numeric_policy_mismatch_fails_closed(self):
        runs = valid_runs()
        runs["meme"]["numeric_policy"]["float_significant_digits"] = 10
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "receipt_contract_mismatch")

    def test_run_receipt_wrong_substrate_identity_fails_closed(self):
        runs = valid_runs()
        runs["meme"] = dict(runs["virus"])
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("meme.substrate", out["mismatched"])

    def test_run_receipt_wrong_parameter_hash_fails_closed(self):
        runs = valid_runs()
        runs["agent"]["parameters_sha256"] = "wrong"
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("agent.parameters_sha256", out["mismatched"])

    def test_run_receipt_missing_declared_metric_fails_closed(self):
        runs = valid_runs()
        del runs["virus"]["metrics"]["cycle_rank_beta1"]
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.cycle_rank_beta1", out["mismatched"])

    def test_run_receipt_wrong_authority_fails_closed(self):
        runs = valid_runs()
        runs["virus"]["scientific_authority"] = "ACCEPT"
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.scientific_authority", out["mismatched"])

    def test_missing_control_receipt_is_unknown(self):
        out = evaluate_research_contract(
            BASE_CONTRACT,
            valid_runs(),
            None,
            valid_witness(),
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "UNKNOWN")
        self.assertEqual(out["reason"], "control_receipt_missing")

    def test_control_receipt_missing_required_control_fails_closed(self):
        control = valid_control_receipt()
        del control["checks"]["topology_only"]
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("checks.topology_only", out["mismatched"])

    def test_control_receipt_wrong_input_hash_fails_closed(self):
        control = valid_control_receipt()
        control["parameters_sha256"] = "wrong"
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("parameters_sha256", out["mismatched"])

    def test_verified_witness_with_wrong_input_hash_fails_closed(self):
        witness = valid_witness()
        witness["inputs"]["graph_sha256"] = "wrong"
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")

    def test_verified_witness_with_wrong_required_check_fails_closed(self):
        witness = valid_witness()
        witness["checks"]["hodge1_nullity"] = 999
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")

    def test_complete_contract_can_pass_without_claiming_truth(self):
        out = evaluate()
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

    def test_dirty_research_qa_surface_is_stale_before_storage_head_can_claim_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            qa = root / "src" / "transmission_ecology" / "research_qa.py"
            qa.parent.mkdir(parents=True)
            qa.write_text("VERSION = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            qa.write_text("VERSION = 2\n", encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_research_qa_surface_dirty")

    def test_dirty_witness_input_is_stale_even_when_experiment_surface_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            witness = root / "receipts" / "independent" / "wolfram-v0.json"
            witness.parent.mkdir(parents=True)
            witness.write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            witness.write_text('{"changed":true}\n', encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_research_input_dirty")

    def test_dirty_reference_receipt_is_stale_even_when_experiment_surface_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            receipt = root / "receipts" / "reference" / "v0-virus.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            receipt.write_text('{"changed":true}\n', encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_research_input_dirty")

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
        witness = valid_witness()
        witness["status"] = "DEGRADED"
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "DEGRADED")
        self.assertEqual(out["authority"], "NONE")

    def test_witness_commit_mismatch_fails_closed(self):
        witness = valid_witness(COMMIT_B)
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_commit_mismatch")

    def test_stored_research_receipt_never_points_to_unbound_evidence(self):
        receipt_path = ROOT / "receipts" / "research-qa" / "v0.json"
        if not receipt_path.is_file():
            return
        qa = json.loads(receipt_path.read_text(encoding="utf-8"))
        storage_head = qa["storage_head"]
        source_commit = qa["source_commit"]
        for relpath in (
            "receipts/reference/v0-virus.json",
            "receipts/reference/v0-meme.json",
            "receipts/reference/v0-agent.json",
            "receipts/reference/v0-controls.json",
            "receipts/independent/wolfram-v0.json",
        ):
            raw = subprocess.check_output(
                ["git", "show", f"{storage_head}:{relpath}"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            evidence = json.loads(raw)
            self.assertEqual(
                evidence["source_commit"],
                source_commit,
                f"{relpath} at storage_head is not bound to the claimed source",
            )

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
        expected_rc = (
            0
            if expected["contract_status"] == "PASS"
            else 1
            if expected["contract_status"] == "FAIL"
            else 2
        )
        self.assertEqual(result.returncode, expected_rc, result.stdout + result.stderr)
        self.assertEqual(payload["contract_status"], expected["contract_status"])
        self.assertEqual(payload["authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
