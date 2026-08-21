import unittest

from matsi.semantic_falsification import run_phase3c


class Phase3CSemanticFalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase3c()

    def test_gate_closes_only_the_semantic_question(self):
        result = self.result
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertFalse(result["gate"]["phase4_started"])
        self.assertTrue(result["closure"]["universal_ir_introduced"] is False)
        self.assertTrue(result["frozen_real_repository_evidence"]["G_digest_matches_phase3b_result"])

    def test_positive_controls_are_observed_and_negative_is_rejected(self):
        evidence = self.result["positive_control_evidence"]
        observations = evidence["observations"]
        self.assertTrue(observations["positive_a"]["matches_oracle"])
        self.assertTrue(observations["positive_b"]["matches_oracle"])
        self.assertFalse(observations["negative_local"]["matches_oracle"])
        self.assertTrue(evidence["negative_control"]["structural_match_to_positive_G"])
        self.assertTrue(evidence["distinguishes_reusable_behavior"])

    def test_real_phase3b_false_positive_remains_unknown(self):
        targets = self.result["frozen_real_repository_evidence"]["targets"]
        for entry_id in ("C", "N1", "N2"):
            self.assertTrue(targets[entry_id]["phase3b_structural_false_positive"])
            self.assertEqual(targets[entry_id]["semantic_evidence"], "UNKNOWN")
            self.assertTrue(targets[entry_id]["matched_units"])
            self.assertTrue(all(row["intervention"]["status"] == "UNKNOWN" for row in targets[entry_id]["matched_units"]))

    def test_provenance_and_semantic_boundary_are_explicit(self):
        result = self.result
        controls = result["positive_control_evidence"]
        self.assertFalse(controls["labels_used_to_discover_G"])
        self.assertTrue(controls["represented_evidence"]["provenance"]["source_ids"])
        self.assertTrue(result["host_represented_derived"]["HOST"])
        self.assertTrue(result["host_represented_derived"]["REPRESENTED"])
        self.assertTrue(result["host_represented_derived"]["DERIVED"])


if __name__ == "__main__":
    unittest.main()
