import copy
import unittest

import numpy as np

from experiments.v1.receipt import (
    POST,
    PRE,
    build_identity_control,
    build_step_receipt,
    evaluate_stage_attribution,
)


class V1ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.x0 = [0.0, 1.0]
        self.V = [[0.95, 0.08], [0.05, 0.92]]
        self.I = np.eye(2).tolist()
        self.W = np.diag([1.0, 0.95]).tolist()

    def receipt(self, source, target):
        return build_step_receipt(
            case_id="case",
            fixture_id="canonical-v1-a1",
            source_revision="f26ba2558b0dd7eff50aad29e8e22c4468b1f0ab",
            state=self.x0,
            variant_transition=self.V,
            source_gate=source,
            target_gate=target,
        )

    def test_each_abc_case_passes_with_its_required_controls(self):
        cases = {
            "target-only": self.receipt(self.I, self.W),
            "source-only": self.receipt(self.W, self.I),
            "two-stage": self.receipt(self.W, self.W),
        }
        for name, receipt in cases.items():
            with self.subTest(name=name):
                controls = {
                    stage: build_identity_control(receipt, stage)
                    for stage in receipt["claimed_stages"]
                }
                result = evaluate_stage_attribution(receipt, controls)
                self.assertEqual(result["stage_attribution"], "PASS", result)
                self.assertEqual(result["scientific_authority"], "NONE")

    def test_missing_required_control_is_unknown(self):
        receipt = self.receipt(self.W, self.W)
        controls = {PRE: build_identity_control(receipt, PRE)}
        result = evaluate_stage_attribution(receipt, controls)
        self.assertEqual(result["stage_attribution"], "UNKNOWN", result)
        self.assertEqual(result["per_stage"][POST], "UNKNOWN")

    def test_supplied_mismatched_control_is_fail(self):
        receipt = self.receipt(self.W, self.W)
        control = build_identity_control(receipt, PRE)
        control["numeric_policy"] = "different"
        result = evaluate_stage_attribution(receipt, {PRE: control, POST: build_identity_control(receipt, POST)})
        self.assertEqual(result["stage_attribution"], "FAIL", result)
        self.assertEqual(result["reason"], f"control_mismatch:{PRE}")

    def test_claimed_stage_tampering_is_fail(self):
        receipt = self.receipt(self.W, self.W)
        receipt["claimed_stages"] = [PRE]
        result = evaluate_stage_attribution(receipt, {})
        self.assertEqual(result["stage_attribution"], "FAIL", result)
        self.assertEqual(result["reason"], "invalid_receipt")

    def test_final_state_only_cannot_pass(self):
        receipt = self.receipt(self.W, self.W)
        for field in ("source_ready", "adapted", "persistent"):
            receipt.pop(field)
        result = evaluate_stage_attribution(receipt, None)
        self.assertEqual(result["stage_attribution"], "UNKNOWN", result)
        self.assertEqual(result["reason"], "stage_witness_missing", result)

    def test_observationally_identical_gate_is_unknown(self):
        source = np.diag([0.5, 1.0]).tolist()
        receipt = self.receipt(source, self.I)
        control = build_identity_control(receipt, PRE)
        result = evaluate_stage_attribution(receipt, {PRE: control})
        self.assertEqual(result["stage_attribution"], "UNKNOWN", result)

    def test_gate_caused_extinction_can_pass(self):
        source = np.diag([1.0, 0.0]).tolist()
        receipt = self.receipt(source, self.I)
        control = build_identity_control(receipt, PRE)
        result = evaluate_stage_attribution(receipt, {PRE: control})
        self.assertEqual(result["stage_attribution"], "PASS", result)


if __name__ == "__main__":
    unittest.main()
