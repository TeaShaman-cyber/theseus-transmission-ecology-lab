import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    "allowed_dispositions": [
        "FOUND_USEFUL_STRUCTURE",
        "NO_SIGNAL",
        "REFINE",
        "REJECT",
        "UNKNOWN_WITHIN_CURRENT_CONTRACT",
    ],
    "experiment_id": "deterministic-v0",
    "question": "Which declared invariants survive substrate change?",
    "hypothesis": "Selected operator-level invariants remain comparable across substrates.",
    "falsifiers": ["shared metrics add no value beyond domain-specific baselines"],
    "declared_metrics": [
        "spectral_radius",
        "cycle_rank_beta1",
        "total_mass_by_step",
        "variant_shannon_entropy",
        "surviving_variant_count",
        "dominant_variant_share",
        "time_to_extinction_or_horizon",
        "perturbation_recovery_ratio",
    ],
    "required_controls": ["subcritical", "supercritical", "topology_only"],
    "limitations": ["linear deterministic model only"],
    "independent_witness": {
        "required": True,
        "kind": "spectral_or_hodge",
        "expected_backend": "WolframLanguageEvaluator",
        "recipe_path": "experiments/v0/witness/wolfram-v0.wl",
        "adapter_path": "experiments/v0/witness/wolfram_v0_adapter.py",
        "witness_schema_version": 2,
        "expected_inputs": {
            "graph_sha256": "graph-ok",
            "controls_sha256": "controls-ok",
        },
        "required_checks": {
            "vertex_count": 4,
            "edge_count": 5,
            "weak_component_count": 1,
            "cycle_rank_beta1": 2,
            "incidence_rank": 3,
            "incidence_nullity": 2,
            "hodge1_nullity": 2,
            "subcritical_spectral_radius": 0.8,
            "supercritical_spectral_radius": 1.2,
            "subcritical_below_one": True,
            "supercritical_above_one": True,
        },
    },
    "receipt_contract": {
        "schema_version": 3,
        "float_significant_digits": 12,
    },
    "metric_semantics": {
        "survival_tolerance": 1e-12,
    },
}

BASE_EXPECTED_METRICS = {
    "spectral_radius": 0.8,
    "subcritical_or_supercritical": "subcritical",
    "cycle_rank_beta1": 2,
    "total_mass_by_step": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2],
    "variant_shannon_entropy": 0.562335144619,
    "surviving_variant_count": 2,
    "dominant_variant_share": 0.75,
    "time_to_extinction_or_horizon": 8,
    "perturbation_recovery_ratio": 0.25,
}


BASE_BINDINGS = {
    "runs": {
        "virus": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "virus-params-ok",
            "variant_count": 2,
            "variants": ["v0", "v1"],
            "seed_variant": "v0",
            "perturbation_recovery_ratio": 0.25,
            "expected_metrics": json.loads(json.dumps(BASE_EXPECTED_METRICS)),
        },
        "meme": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "meme-params-ok",
            "variant_count": 2,
            "variants": ["m0", "m1"],
            "seed_variant": "m0",
            "perturbation_recovery_ratio": 0.25,
            "expected_metrics": json.loads(json.dumps(BASE_EXPECTED_METRICS)),
        },
        "agent": {
            "contract_sha256": "contract-ok",
            "graph_sha256": "graph-ok",
            "parameters_sha256": "agent-params-ok",
            "variant_count": 2,
            "variants": ["a0", "a1"],
            "seed_variant": "a0",
            "perturbation_recovery_ratio": 0.25,
            "expected_metrics": json.loads(json.dumps(BASE_EXPECTED_METRICS)),
        },
    },
    "witness": {
        "recipe_path": "experiments/v0/witness/wolfram-v0.wl",
        "recipe_sha256": "recipe-ok",
        "adapter_path": "experiments/v0/witness/wolfram_v0_adapter.py",
        "adapter_sha256": "adapter-ok",
        "required_checks": dict(BASE_CONTRACT["independent_witness"]["required_checks"]),
    },
    "control": {
        "graph_sha256": "graph-ok",
        "parameters_sha256": "controls-ok",
        "subcritical_target_radius": 0.8,
        "supercritical_target_radius": 1.2,
        "variant_count": 2,
        "horizon": 8,
        "run_initial_mass": 1.0,
        "run_seed_node": "n1",
        "expected_checks": {
            "subcritical": {
                "spectral_radius": 0.8,
                "initial_mass": 1.0,
                "final_mass": 0.5,
            },
            "supercritical": {
                "spectral_radius": 1.2,
                "initial_mass": 1.0,
                "final_mass": 2.0,
            },
        },
    },
}


def run_receipt(
    name: str,
    commit: str = COMMIT_A,
    *,
    all_passed: bool = True,
    schema_version: int = 3,
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
        "horizon": 8,
        "initial_condition": {
            "node": "n1",
            "variant": binding["seed_variant"],
            "mass": 1.0,
        },
        "metrics": {
            "spectral_radius": 0.8,
            "subcritical_or_supercritical": "subcritical",
            "cycle_rank_beta1": 2,
            "total_mass_by_step": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2],
            "variant_shannon_entropy": 0.562335144619,
            "surviving_variant_count": 2,
            "dominant_variant_share": 0.75,
            "time_to_extinction_or_horizon": 8,
            "perturbation_recovery_ratio": 0.25,
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
        "schema_version": 3,
        "numeric_policy": {"float_significant_digits": 12},
        "experiment_id": "deterministic-v0",
        "source_commit": commit,
        "graph_sha256": "graph-ok",
        "parameters_sha256": "controls-ok",
        "scientific_authority": "NONE",
        "all_passed": True,
        "checks": {
            "subcritical": {
                "spectral_radius": 0.8,
                "initial_mass": 1.0,
                "final_mass": 0.5,
            },
            "supercritical": {
                "spectral_radius": 1.2,
                "initial_mass": 1.0,
                "final_mass": 2.0,
            },
            "topology_only": {
                "graph_sha256": "graph-ok",
                "subcritical_graph_sha256": "graph-ok",
                "supercritical_graph_sha256": "graph-ok",
                "cycle_rank_beta1": 2,
                "subcritical_cycle_rank_beta1": 2,
                "supercritical_cycle_rank_beta1": 2,
                "subcritical_regime": "decay",
                "supercritical_regime": "growth",
                "same_topology": True,
                "opposite_regimes": True,
                "topology_only_explanation_rejected": True,
            },
        },
    }


def valid_witness(commit: str = COMMIT_A):
    return {
        "schema_version": 2,
        "experiment_id": "deterministic-v0",
        "source_commit": commit,
        "status": "VERIFIED",
        "authority": "NONE",
        "scientific_authority": "NONE",
        "backend": "WolframLanguageEvaluator",
        "recipe_sha256": "recipe-ok",
        "adapter_sha256": "adapter-ok",
        "kind": "spectral_or_hodge",
        "inputs": {
            "graph_sha256": "graph-ok",
            "controls_sha256": "controls-ok",
        },
        "checks": {
            "vertex_count": 4,
            "edge_count": 5,
            "weak_component_count": 1,
            "cycle_rank_beta1": 2,
            "incidence_rank": 3,
            "incidence_nullity": 2,
            "hodge1_nullity": 2,
            "subcritical_spectral_radius": 0.8,
            "supercritical_spectral_radius": 1.2,
            "subcritical_below_one": True,
            "supercritical_above_one": True,
        },
        "observed": {
            "vertex_count": 4,
            "edge_count": 5,
            "weak_component_count": 1,
            "cycle_rank_beta1": 2,
            "incidence_rank": 3,
            "incidence_nullity": 2,
            "hodge1_nullity": 2,
            "subcritical_spectral_radius": 0.8,
            "supercritical_spectral_radius": 1.2,
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
    def test_run_receipt_schema_and_digits_require_integer_domain(self):
        mutations = (
            ("schema_version", lambda receipt: receipt.__setitem__("schema_version", 3.0)),
            (
                "numeric_policy.float_significant_digits",
                lambda receipt: receipt["numeric_policy"].__setitem__(
                    "float_significant_digits", 12.0
                ),
            ),
            ("horizon", lambda receipt: receipt.__setitem__("horizon", 8.0)),
        )
        for expected_field, mutate in mutations:
            with self.subTest(expected_field=expected_field):
                runs = valid_runs()
                mutate(runs["virus"])
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)

    def test_witness_schema_version_requires_integer_domain(self):
        witness = valid_witness()
        witness["schema_version"] = 2.0
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertIn("schema_version", out["mismatched"], out)

    def test_non_object_numeric_policy_fails_closed(self):
        for value in (None, 12, [], "twelve"):
            with self.subTest(value=repr(value)):
                runs = valid_runs()
                runs["virus"]["numeric_policy"] = value
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "receipt_contract_mismatch", out)
                self.assertIn("virus", out["mismatched"], out)

    def test_extreme_witness_observation_fails_closed(self):
        witness = valid_witness()
        witness["observed"]["edge_count"] = 10 ** 400
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "witness_content_mismatch", out)
        self.assertIn("observed.edge_count", out["mismatched"], out)

    def test_large_numeric_evidence_fails_closed_without_overflow(self):
        huge = 10 ** 400
        runs = valid_runs()
        runs["virus"]["metrics"]["spectral_radius"] = huge
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL", out)
        control = valid_control_receipt()
        control["checks"]["subcritical"]["spectral_radius"] = huge
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL", out)

    def test_source_metric_rounding_accepts_only_canonical_receipt_value(self):
        expected = 1.0376324719148955
        from transmission_ecology.research_qa import _matches_rounded_numeric

        self.assertTrue(_matches_rounded_numeric(1.03763247191, expected, 12))
        self.assertFalse(_matches_rounded_numeric(1.03763247192, expected, 12))
        self.assertFalse(_matches_rounded_numeric(1.03763247190, expected, 12))

    def test_source_replay_rejects_corrupted_declared_run_metrics(self):
        cases = []
        runs = valid_runs()
        runs["virus"]["metrics"]["spectral_radius"] = 999.0
        runs["virus"]["metrics"]["subcritical_or_supercritical"] = "supercritical"
        cases.append(("spectral_radius", runs))

        runs = valid_runs()
        trace = runs["virus"]["metrics"]["total_mass_by_step"]
        trace[1:-1] = [777.0] * (len(trace) - 2)
        cases.append(("total_mass_by_step", runs))

        runs = valid_runs()
        metrics = runs["virus"]["metrics"]
        metrics["surviving_variant_count"] = 2
        metrics["dominant_variant_share"] = 0.5
        metrics["variant_shannon_entropy"] = 0.69314718056
        cases.append(("diversity", runs))

        for label, runs in cases:
            with self.subTest(label=label):
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "run_receipt_binding_mismatch", out)

    def test_v0_contract_schema_version_rejects_boolean_alias(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["schema_version"] = True
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            valid_witness(),
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
        self.assertIn("schema_version", out["mismatched"], out)

    def test_v0_witness_huge_integer_fails_closed_without_overflow(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        huge = 10 ** 10000
        contract["independent_witness"]["required_checks"][
            "weak_component_count"
        ] = huge
        witness = valid_witness()
        witness["checks"]["weak_component_count"] = huge
        witness["observed"]["weak_component_count"] = huge
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
        self.assertIn(
            "independent_witness.required_checks.values",
            out["mismatched"],
            out,
        )

    def test_v0_witness_numeric_checks_reject_boolean_aliases(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"]["required_checks"]["weak_component_count"] = True
        witness = valid_witness()
        witness["checks"]["weak_component_count"] = True
        witness["observed"].pop("weak_component_count")
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
        self.assertIn(
            "independent_witness.required_checks.values",
            out["mismatched"],
            out,
        )

    def test_v0_witness_check_values_use_type_sensitive_equality(self):
        witness = valid_witness()
        witness["checks"]["weak_component_count"] = True
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "witness_content_mismatch", out)
        self.assertIn("checks.weak_component_count", out["mismatched"], out)

    def test_v0_witness_expectations_must_match_source_derived_semantics(self):
        mutations = (
            ("edge_count", 999),
            ("subcritical_spectral_radius", 0.7),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                contract = json.loads(json.dumps(BASE_CONTRACT))
                contract["independent_witness"]["required_checks"][key] = value
                witness = valid_witness()
                witness["checks"][key] = value
                if key in witness["observed"]:
                    witness["observed"][key] = value
                out = evaluate_research_contract(
                    contract,
                    valid_runs(),
                    valid_control_receipt(),
                    witness,
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
                self.assertIn(
                    "independent_witness.required_checks.values",
                    out["mismatched"],
                    out,
                )

    def test_v0_contract_profile_cannot_silently_shrink(self):
        mutations = []

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract.pop("schema_version")
        mutations.append(("schema_version", contract))

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["allowed_dispositions"].remove("UNKNOWN_WITHIN_CURRENT_CONTRACT")
        mutations.append(("allowed_dispositions", contract))

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["declared_metrics"].remove("perturbation_recovery_ratio")
        mutations.append(("declared_metrics", contract))

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["required_controls"].remove("topology_only")
        mutations.append(("required_controls", contract))

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"].pop("required")
        mutations.append(("independent_witness.required", contract))

        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"]["required_checks"].pop("edge_count")
        mutations.append(("independent_witness.required_checks", contract))

        for expected_field, contract in mutations:
            with self.subTest(expected_field=expected_field):
                out = evaluate_research_contract(
                    contract,
                    valid_runs(),
                    valid_control_receipt(),
                    valid_witness(),
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
                self.assertIn(expected_field, out["mismatched"], out)

    def test_contract_profile_lists_reject_non_string_entries_without_crashing(self):
        mutations = []
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["allowed_dispositions"][0] = []
        mutations.append(("allowed_dispositions", contract))
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["declared_metrics"][0] = []
        mutations.append(("declared_metrics", contract))
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["required_controls"][0] = {}
        mutations.append(("required_controls", contract))

        for expected_field, contract in mutations:
            with self.subTest(expected_field=expected_field):
                out = evaluate_research_contract(
                    contract,
                    valid_runs(),
                    valid_control_receipt(),
                    valid_witness(),
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "invalid_v0_contract_profile", out)
                self.assertIn(expected_field, out["mismatched"], out)

    def test_non_object_receipt_contract_fails_closed(self):
        for bad_value in (True, 1, ["schema_version"]):
            with self.subTest(bad_value=bad_value):
                contract = json.loads(json.dumps(BASE_CONTRACT))
                contract["receipt_contract"] = bad_value
                out = evaluate_research_contract(
                    contract,
                    valid_runs(),
                    valid_control_receipt(),
                    valid_witness(),
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "invalid_receipt_contract", out)

    def test_contract_shape_property_sweep_fails_closed(self):
        bad_json_scalars = (None, True, 0, 1.5, "", [], {})
        for field in (
            "allowed_dispositions",
            "declared_metrics",
            "required_controls",
        ):
            for bad_value in bad_json_scalars:
                with self.subTest(field=field, bad_value=bad_value):
                    contract = json.loads(json.dumps(BASE_CONTRACT))
                    contract[field][0] = bad_value
                    out = evaluate_research_contract(
                        contract,
                        valid_runs(),
                        valid_control_receipt(),
                        valid_witness(),
                        source_commit=COMMIT_A,
                        evidence_bindings=BASE_BINDINGS,
                    )
                    self.assertNotEqual(out["contract_status"], "PASS", out)

        for bad_value in (True, 1, 1.5, "receipt", [], ["schema_version"]):
            with self.subTest(field="receipt_contract", bad_value=bad_value):
                contract = json.loads(json.dumps(BASE_CONTRACT))
                contract["receipt_contract"] = bad_value
                out = evaluate_research_contract(
                    contract,
                    valid_runs(),
                    valid_control_receipt(),
                    valid_witness(),
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertNotEqual(out["contract_status"], "PASS", out)

    def test_cross_layer_provenance_mutation_matrix_fails_closed(self):
        cases = []

        runs = valid_runs()
        runs["virus"]["contract_sha256"] = "wrong-contract"
        cases.append(("run.contract_sha256", runs, valid_control_receipt(), valid_witness()))

        runs = valid_runs()
        runs["virus"]["graph_sha256"] = "wrong-graph"
        cases.append(("run.graph_sha256", runs, valid_control_receipt(), valid_witness()))

        runs = valid_runs()
        runs["virus"]["parameters_sha256"] = "wrong-parameters"
        cases.append(("run.parameters_sha256", runs, valid_control_receipt(), valid_witness()))

        control = valid_control_receipt()
        control["graph_sha256"] = "wrong-graph"
        cases.append(("control.graph_sha256", valid_runs(), control, valid_witness()))

        control = valid_control_receipt()
        control["parameters_sha256"] = "wrong-parameters"
        cases.append(("control.parameters_sha256", valid_runs(), control, valid_witness()))

        witness = valid_witness()
        witness["recipe_sha256"] = "wrong-recipe"
        cases.append(("witness.recipe_sha256", valid_runs(), valid_control_receipt(), witness))

        witness = valid_witness()
        witness["adapter_sha256"] = "wrong-adapter"
        cases.append(("witness.adapter_sha256", valid_runs(), valid_control_receipt(), witness))

        witness = valid_witness()
        witness["inputs"]["graph_sha256"] = "wrong-graph"
        cases.append(("witness.inputs.graph_sha256", valid_runs(), valid_control_receipt(), witness))

        witness = valid_witness()
        witness["inputs"]["controls_sha256"] = "wrong-controls"
        cases.append(("witness.inputs.controls_sha256", valid_runs(), valid_control_receipt(), witness))

        for label, runs, control, witness in cases:
            with self.subTest(label=label):
                out = evaluate_research_contract(
                    BASE_CONTRACT,
                    runs,
                    control,
                    witness,
                    source_commit=COMMIT_A,
                    evidence_bindings=BASE_BINDINGS,
                )
                self.assertNotEqual(out["contract_status"], "PASS", out)

    def test_survivor_count_property_sweep_fails_closed(self):
        for bad_value in (3, 999, 10 ** 20, 10 ** 100, 10 ** 400):
            with self.subTest(bad_value=str(bad_value)[:32]):
                runs = valid_runs()
                runs["virus"]["metrics"]["surviving_variant_count"] = bad_value
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertIn(
                    "virus.metrics.surviving_variant_count",
                    out["mismatched"],
                    out,
                )

    def test_nonfinite_contract_metadata_fails_closed(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["question"] = float("nan")
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            valid_witness(),
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "invalid_contract_metadata")
        self.assertIn("question", out["mismatched"])

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

    def test_symbolic_source_commit_is_rejected(self):
        source = "HEAD"
        out = evaluate_research_contract(
            BASE_CONTRACT,
            valid_runs(source),
            valid_control_receipt(source),
            valid_witness(source),
            source_commit=source,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "invalid_source_commit", out)

    def test_experiment_id_is_required_typed_metadata(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract.pop("experiment_id")
        runs = valid_runs()
        for receipt in runs.values():
            receipt.pop("experiment_id")
        control = valid_control_receipt()
        control.pop("experiment_id")
        witness = valid_witness()
        witness.pop("experiment_id")
        out = evaluate_research_contract(
            contract,
            runs,
            control,
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertIn(out["reason"], {"missing_contract_fields", "invalid_contract_metadata"}, out)

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

    def test_run_receipt_initial_condition_must_match_source_identities(self):
        for field, value in (("node", "n4"), ("variant", "v1"), ("mass", 2.0)):
            with self.subTest(field=field):
                runs = valid_runs()
                runs["virus"]["initial_condition"][field] = value
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "run_receipt_binding_mismatch", out)
                self.assertIn(f"virus.initial_condition.{field}", out["mismatched"], out)

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

    def test_declared_metric_values_fail_closed_on_corruption(self):
        corruptions = {
            "spectral_radius": None,
            "cycle_rank_beta1": 2.5,
            "total_mass_by_step": [1.0, float("nan")],
            "variant_shannon_entropy": 10.0,
            "surviving_variant_count": -1,
            "dominant_variant_share": 1.5,
            "time_to_extinction_or_horizon": 9,
            "perturbation_recovery_ratio": -0.1,
        }
        for metric, bad_value in corruptions.items():
            with self.subTest(metric=metric):
                runs = valid_runs()
                runs["virus"]["metrics"][metric] = bad_value
                out = evaluate(runs=runs)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "run_receipt_binding_mismatch", out)
                self.assertIn(f"virus.metrics.{metric}", out["mismatched"], out)

    def test_total_mass_shape_must_match_horizon(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["total_mass_by_step"] = [1.0, 0.5]
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertIn("virus.metrics.total_mass_by_step", out["mismatched"])

    def test_survivor_count_cannot_exceed_source_variant_count(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["surviving_variant_count"] = 999
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.surviving_variant_count", out["mismatched"])

    def test_extreme_survivor_count_fails_closed_without_float_overflow(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["surviving_variant_count"] = 10 ** 400
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch", out)
        self.assertIn("virus.metrics.surviving_variant_count", out["mismatched"], out)

    def test_extinction_time_must_match_mass_trace(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["time_to_extinction_or_horizon"] = 0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.time_to_extinction_or_horizon", out["mismatched"])

    def test_run_horizon_must_match_source_control_horizon(self):
        runs = valid_runs()
        for receipt in runs.values():
            receipt["horizon"] = 0
            receipt["metrics"]["total_mass_by_step"] = [1.0]
            receipt["metrics"]["time_to_extinction_or_horizon"] = 0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.horizon", out["mismatched"])

    def test_mass_trace_initial_value_must_match_source_initial_mass(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["total_mass_by_step"] = [999.0] * 9
        runs["virus"]["metrics"]["time_to_extinction_or_horizon"] = 8
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.total_mass_by_step", out["mismatched"])

    def test_dominant_share_must_be_consistent_with_source_variant_count(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["surviving_variant_count"] = 2
        runs["virus"]["metrics"]["dominant_variant_share"] = 0.0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.dominant_variant_share", out["mismatched"])

    def test_dominant_share_must_respect_reported_survivor_count(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["surviving_variant_count"] = 1
        runs["virus"]["metrics"]["dominant_variant_share"] = 0.5
        runs["virus"]["metrics"]["variant_shannon_entropy"] = 0.0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.dominant_variant_share", out["mismatched"])

    def test_entropy_must_be_jointly_consistent_with_dominant_share(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["surviving_variant_count"] = 2
        runs["virus"]["metrics"]["dominant_variant_share"] = 0.5
        runs["virus"]["metrics"]["variant_shannon_entropy"] = 0.0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.variant_shannon_entropy", out["mismatched"])

    def test_zero_survivors_reject_dominant_mass_above_tolerance(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["total_mass_by_step"] = [
            1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625, 0.0078125, 2e-12
        ]
        runs["virus"]["metrics"]["time_to_extinction_or_horizon"] = 8
        runs["virus"]["metrics"]["surviving_variant_count"] = 0
        runs["virus"]["metrics"]["dominant_variant_share"] = 0.75
        runs["virus"]["metrics"]["variant_shannon_entropy"] = 0.562335144619
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.surviving_variant_count", out["mismatched"])

    def test_multiple_survivors_require_non_dominant_mass_above_tolerance(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["total_mass_by_step"] = [1.0] * 9
        runs["virus"]["metrics"]["time_to_extinction_or_horizon"] = 8
        runs["virus"]["metrics"]["surviving_variant_count"] = 2
        runs["virus"]["metrics"]["dominant_variant_share"] = 1.0
        runs["virus"]["metrics"]["variant_shannon_entropy"] = 0.0
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.dominant_variant_share", out["mismatched"])

    def test_perturbation_recovery_ratio_must_match_source_binding(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["perturbation_recovery_ratio"] = 0.9
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch", out)
        self.assertIn("virus.metrics.perturbation_recovery_ratio", out["mismatched"], out)

    def test_survivor_floor_uses_receipt_scale_rounding_not_fixed_slack(self):
        runs = valid_runs()
        runs["virus"]["metrics"]["total_mass_by_step"] = [1.0] * 9
        runs["virus"]["metrics"]["time_to_extinction_or_horizon"] = 8
        runs["virus"]["metrics"]["surviving_variant_count"] = 1
        runs["virus"]["metrics"]["dominant_variant_share"] = 0.9999999999
        runs["virus"]["metrics"]["variant_shannon_entropy"] = 2.40258528351e-09
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.dominant_variant_share", out["mismatched"])

    def test_run_receipt_wrong_authority_fails_closed(self):
        runs = valid_runs()
        runs["virus"]["scientific_authority"] = "ACCEPT"
        out = evaluate(runs=runs)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.scientific_authority", out["mismatched"])

    def test_metric_semantics_tolerance_must_match_canonical_definition(self):
        with patch("transmission_ecology.research_qa.SURVIVAL_TOLERANCE", 1e-6):
            out = evaluate()
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "metric_semantics_mismatch")
        self.assertIn("survival_tolerance", out["mismatched"])

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

    def test_control_receipt_empty_named_checks_fail_closed(self):
        control = valid_control_receipt()
        control["checks"] = {
            "subcritical": {},
            "supercritical": {},
            "topology_only": {},
        }
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("checks.subcritical.spectral_radius", out["mismatched"])
        self.assertIn("checks.supercritical.spectral_radius", out["mismatched"])

    def test_control_radii_must_match_registered_targets(self):
        control = valid_control_receipt()
        control["checks"]["subcritical"]["spectral_radius"] = 0.2
        control["checks"]["supercritical"]["spectral_radius"] = 7.0
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("checks.subcritical.spectral_radius_target", out["mismatched"])
        self.assertIn("checks.supercritical.spectral_radius_target", out["mismatched"])

    def test_control_receipt_false_mass_direction_fails_closed(self):
        control = valid_control_receipt()
        control["checks"]["subcritical"] = {
            "spectral_radius": 0.8,
            "initial_mass": 1.0,
            "final_mass": 2.0,
        }
        control["checks"]["supercritical"] = {
            "spectral_radius": 1.2,
            "initial_mass": 1.0,
            "final_mass": 0.5,
        }
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("checks.subcritical.decay", out["mismatched"])
        self.assertIn("checks.supercritical.growth", out["mismatched"])

    def test_control_receipt_wrong_input_hash_fails_closed(self):
        control = valid_control_receipt()
        control["parameters_sha256"] = "wrong"
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("parameters_sha256", out["mismatched"])

    def test_coordinated_false_beta_cannot_pass_controls_and_runs(self):
        runs = valid_runs()
        for receipt in runs.values():
            receipt["metrics"]["cycle_rank_beta1"] = 999
        control = valid_control_receipt()
        topology = control["checks"]["topology_only"]
        for field in (
            "cycle_rank_beta1",
            "subcritical_cycle_rank_beta1",
            "supercritical_cycle_rank_beta1",
        ):
            topology[field] = 999
        out = evaluate(runs=runs, control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "run_receipt_binding_mismatch")
        self.assertIn("virus.metrics.cycle_rank_beta1", out["mismatched"])

    def test_witness_observed_cannot_contradict_verified_checks(self):
        witness = valid_witness()
        witness["observed"]["cycle_rank_beta1"] = 999
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")
        self.assertIn("observed.cycle_rank_beta1", out["mismatched"])

    def test_witness_requires_every_direct_numeric_observation(self):
        for key in ("cycle_rank_beta1", "hodge1_nullity"):
            with self.subTest(key=key):
                witness = valid_witness()
                del witness["observed"][key]
                out = evaluate(witness=witness)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "witness_content_mismatch", out)
                self.assertIn(f"observed.{key}", out["mismatched"], out)

    def test_witness_scientific_authority_must_remain_none(self):
        witness = valid_witness()
        witness["scientific_authority"] = "ACCEPT"
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")
        self.assertIn("scientific_authority", out["mismatched"])

    def test_witness_backend_must_match_preregistered_backend(self):
        for backend in (None, "NumPy"):
            with self.subTest(backend=backend):
                witness = valid_witness()
                if backend is None:
                    witness.pop("backend")
                else:
                    witness["backend"] = backend
                out = evaluate(witness=witness)
                self.assertEqual(out["contract_status"], "FAIL", out)
                self.assertEqual(out["reason"], "witness_content_mismatch", out)
                self.assertIn("backend", out["mismatched"], out)

    def test_witness_adapter_digest_must_bind_source_adapter(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"]["adapter_path"] = (
            "experiments/v0/witness/wolfram_v0_adapter.py"
        )
        contract["independent_witness"]["witness_schema_version"] = 2
        bindings = json.loads(json.dumps(BASE_BINDINGS))
        bindings["witness"]["adapter_path"] = (
            "experiments/v0/witness/wolfram_v0_adapter.py"
        )
        bindings["witness"]["adapter_sha256"] = "adapter-ok"
        witness = valid_witness()
        witness["schema_version"] = 2
        witness["adapter_sha256"] = "wrong-adapter"
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=bindings,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "witness_content_mismatch", out)
        self.assertIn("adapter_sha256", out["mismatched"], out)

    def test_witness_schema_version_must_match_contract(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"]["adapter_path"] = (
            "experiments/v0/witness/wolfram_v0_adapter.py"
        )
        contract["independent_witness"]["witness_schema_version"] = 2
        bindings = json.loads(json.dumps(BASE_BINDINGS))
        bindings["witness"]["adapter_path"] = (
            "experiments/v0/witness/wolfram_v0_adapter.py"
        )
        bindings["witness"]["adapter_sha256"] = "adapter-ok"
        witness = valid_witness()
        witness["schema_version"] = 1
        witness["adapter_sha256"] = "adapter-ok"
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=bindings,
        )
        self.assertEqual(out["contract_status"], "FAIL", out)
        self.assertEqual(out["reason"], "witness_content_mismatch", out)
        self.assertIn("schema_version", out["mismatched"], out)

    def test_witness_recipe_digest_must_bind_source_recipe(self):
        witness = valid_witness()
        witness["recipe_sha256"] = "wrong-recipe"
        out = evaluate(witness=witness)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")
        self.assertIn("recipe_sha256", out["mismatched"])

    def test_witness_and_contract_cannot_collude_on_stale_source_hashes(self):
        contract = json.loads(json.dumps(BASE_CONTRACT))
        contract["independent_witness"]["expected_inputs"] = {
            "graph_sha256": "stale-graph",
            "controls_sha256": "stale-controls",
        }
        witness = valid_witness()
        witness["inputs"] = {
            "graph_sha256": "stale-graph",
            "controls_sha256": "stale-controls",
        }
        out = evaluate_research_contract(
            contract,
            valid_runs(),
            valid_control_receipt(),
            witness,
            source_commit=COMMIT_A,
            evidence_bindings=BASE_BINDINGS,
        )
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "witness_content_mismatch")
        self.assertTrue(
            any(item.endswith(".source_binding") for item in out["mismatched"]),
            out,
        )

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

    def test_dirty_python_startup_hook_is_part_of_execution_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            hook = root / "src" / "sitecustomize.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            hook.write_text("VALUE = 2\n", encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_experiment_surface_dirty")

    def test_dirty_arbitrary_package_module_is_part_of_execution_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            helper = root / "src" / "transmission_ecology" / "future_helper.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            helper.write_text("VALUE = 2\n", encoding="utf-8")
            currentness, reason = _source_currentness(root, head, head)
            self.assertEqual(currentness, "STALE")
            self.assertEqual(reason, "working_tree_experiment_surface_dirty")

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


    def test_control_receipt_arbitrary_masses_fail_source_replay(self):
        control = valid_control_receipt()
        control["checks"]["subcritical"]["initial_mass"] = 999.0
        control["checks"]["subcritical"]["final_mass"] = 1.0
        control["checks"]["supercritical"]["initial_mass"] = 1.0
        control["checks"]["supercritical"]["final_mass"] = 999.0
        out = evaluate(control=control)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "control_receipt_binding_mismatch")
        self.assertIn("checks.subcritical.initial_mass.source", out["mismatched"])
        self.assertIn("checks.supercritical.final_mass.source", out["mismatched"])

    def test_build_current_receipt_non_object_run_fails_closed(self):
        original = __import__(
            "transmission_ecology.research_qa", fromlist=["_maybe_load"]
        )._maybe_load

        def malformed_virus(path):
            if path.name == "v0-virus.json":
                return []
            return original(path)

        with (
            patch("transmission_ecology.research_qa._maybe_load", side_effect=malformed_virus),
            patch(
                "transmission_ecology.research_qa._source_currentness",
                return_value=("BOUND_UNCHANGED_SURFACE", None),
            ),
        ):
            out = build_current_receipt(ROOT)
        self.assertEqual(out["contract_status"], "FAIL")
        self.assertEqual(out["reason"], "invalid_run_receipt_type")
        self.assertIn("virus.receipt", out["mismatched"])

    def test_stored_research_receipt_binds_current_evidence_content(self):
        receipt_path = ROOT / "receipts" / "research-qa" / "v0.json"
        if not receipt_path.is_file():
            return
        qa = json.loads(receipt_path.read_text(encoding="utf-8"))
        source_commit = qa["source_commit"]
        snapshot = qa["evidence_snapshot"]
        expected_paths = (
            "receipts/reference/v0-virus.json",
            "receipts/reference/v0-meme.json",
            "receipts/reference/v0-agent.json",
            "receipts/reference/v0-controls.json",
            "receipts/independent/wolfram-v0.json",
        )
        self.assertEqual(set(snapshot), set(expected_paths))
        for relpath in expected_paths:
            path = ROOT / relpath
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), snapshot[relpath])
            evidence = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                evidence["source_commit"],
                source_commit,
                f"{relpath} is not bound to the claimed source",
            )

    def test_verify_stored_receipt_survives_squash_when_content_matches(self):
        check = ROOT / "tools" / "research" / "check"
        durable = build_current_receipt(ROOT)
        durable["storage_head"] = "f" * 40
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v0.json"
            path.write_text(
                json.dumps(durable, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(check), "--verify-stored", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["verification_status"], "PASS")

    def test_verify_stored_receipt_rejects_snapshot_tampering(self):
        check = ROOT / "tools" / "research" / "check"
        durable = build_current_receipt(ROOT)
        first = sorted(durable["evidence_snapshot"])[0]
        durable["evidence_snapshot"][first] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v0.json"
            path.write_text(
                json.dumps(durable, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(check), "--verify-stored", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["verification_status"], "FAIL")
        self.assertIn("evidence_snapshot", payload["mismatched"])

    def test_verify_stored_receipt_accepts_current_durable_receipt(self):
        check = ROOT / "tools" / "research" / "check"
        receipt = ROOT / "receipts" / "research-qa" / "v0.json"
        result = subprocess.run(
            [str(check), "--verify-stored", str(receipt)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["verification_status"], "PASS")

    def test_verify_stored_receipt_rejects_semantic_tampering(self):
        check = ROOT / "tools" / "research" / "check"
        durable = json.loads(
            (ROOT / "receipts" / "research-qa" / "v0.json").read_text(encoding="utf-8")
        )
        durable["authority"] = "ROOT"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v0.json"
            path.write_text(
                json.dumps(durable, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(check), "--verify-stored", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["verification_status"], "FAIL")
        self.assertIn("authority", payload["mismatched"])

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
