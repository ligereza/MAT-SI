import unittest

from matsi.evidence_discovery import run_phase3d


class Phase3DEvidenceDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase3d()

    def test_hypotheses_are_derived_without_the_sealed_oracle(self):
        result = self.result
        self.assertFalse(result["frozen_inputs"]["expected_outputs_used_before_discovery"])
        self.assertFalse(result["frozen_inputs"]["semantic_labels_used_before_discovery"])
        self.assertFalse(result["frozen_inputs"]["manual_relation_used_before_discovery"])
        self.assertEqual(result["discovery"]["candidate_count"], 3)
        for hypothesis in result["discovery"]["candidate_hypotheses"]:
            self.assertEqual(hypothesis["coverage"], 4)
            self.assertEqual(len(hypothesis["evidence_for"]), 4)
            self.assertEqual(hypothesis["evidence_against"], [])
            self.assertGreater(hypothesis["description_cost"], 0)

    def test_frozen_hypotheses_survive_held_out_without_mutation(self):
        result = self.result
        evaluations = result["held_out"]["evaluations"]
        self.assertTrue(all(item["status"] == "SURVIVED" for item in evaluations))
        self.assertFalse(result["frozen_hypotheses"]["changed_after_held_out"])
        self.assertEqual(
            {item["provenance"]["input_set"] for item in evaluations},
            {"frozen_held_out"},
        )

    def test_behavior_rejects_structural_negative(self):
        negative = self.result["negative_control"]
        self.assertTrue(negative["structural_match_to_G"])
        self.assertTrue(negative["behavioral_distinction_observed"])
        self.assertIn("pair_output_==", negative["discriminating_hypothesis_ids"])
        statuses = {item["hypothesis_id"]: item["status"] for item in negative["evaluations"]}
        self.assertEqual(statuses["pair_output_=="], "FALSIFIED")
        self.assertEqual(statuses["pair_output_<="], "SURVIVED")

    def test_oracle_is_only_final_validation(self):
        result = self.result
        self.assertEqual(
            result["phase_order"][-1],
            "sealed_oracle_validation",
        )
        oracle = result["sealed_oracle_validation"]
        self.assertTrue(oracle["opened_after_discovery_and_held_out"])
        self.assertTrue(oracle["A_equals_B_on_oracle"])
        self.assertTrue(oracle["discovered_claim_validated"])
        self.assertFalse(oracle["stronger_semantic_description_claimed"])

    def test_real_G_has_no_observable_correspondence_and_llm_is_not_evidence(self):
        result = self.result
        real_g = result["real_phase3b_G_information_test"]
        self.assertEqual(
            real_g["status"],
            "STRUCTURE_FOUND_BUT_NO_OBSERVABLE_CORRESPONDENCE_CAN_BE_DERIVED",
        )
        self.assertEqual(real_g["falsifiable_behavioral_hypotheses_generated"], [])
        self.assertFalse(result["llm_boundary"]["confidence_is_evidence"])
        self.assertFalse(result["llm_boundary"]["llm_integration_built"])
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertFalse(result["gate"]["phase4_started"])


if __name__ == "__main__":
    unittest.main()
