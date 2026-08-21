import unittest

from matsi.cross_domain import run_phase4


class Phase4CrossDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase4()

    def test_blind_envelope_preserves_observables_and_records_residue(self):
        result = self.result
        self.assertEqual(
            result["common_experience_envelope"]["fields"],
            ["context", "observation", "action", "outcome", "cost", "provenance"],
        )
        self.assertFalse(result["blind_pass"]["domain_names_visible_to_discovery"])
        self.assertTrue(result["blind_pass"]["chronology_and_transitions_preserved"])
        for audit in result["adapter_audit"].values():
            self.assertTrue(audit["PRESERVED"])
            self.assertTrue(audit["NORMALIZED"])
            self.assertTrue(audit["LOST"])
            self.assertTrue(audit["RESIDUE"])

    def test_G_is_discovered_from_A_B_and_frozen_before_C(self):
        result = self.result
        G = result["frozen_G"]["G"]
        self.assertEqual(set(G["provenance"]["source_ids"]), {"A", "B"})
        self.assertEqual(G["generated_from"], "blind_A_B_observations")
        self.assertTrue(result["frozen_G"]["C_was_loaded_after_freeze"])
        self.assertFalse(result["frozen_G"]["changed_after_C"])
        self.assertTrue(result["discovery_from_A_B"]["candidate_count"] > 0)
        for candidate in result["discovery_from_A_B"]["atomic_candidates"]:
            self.assertTrue(candidate["evidence_for"])
            self.assertEqual(candidate["evidence_against"], [])
            self.assertGreater(candidate["cost"], 0)
            self.assertTrue(candidate["residue"])
            self.assertTrue(candidate["provenance"])

    def test_structural_behavioral_and_predictive_transfer_are_separate(self):
        result = self.result
        transfer = result["transfer"]
        self.assertEqual(transfer["STRUCTURAL_TRANSFER"]["status"], "OBSERVED")
        self.assertEqual(transfer["BEHAVIORAL_TRANSFER"]["status"], "OBSERVED")
        self.assertEqual(transfer["PREDICTIVE_TRANSFER"]["status"], "OBSERVED")
        metrics = result["held_out_C"]["prediction_metrics"]
        self.assertEqual(metrics["matched_windows"], 3)
        self.assertEqual(metrics["G_prediction_accuracy_on_matched_windows"], 2 / 3)
        self.assertEqual(metrics["no_G_baseline_modal_accuracy_over_all_C_windows"], 0.5)
        self.assertGreater(metrics["predictive_gain"], 0)

    def test_productive_repetition_is_a_negative_control(self):
        result = self.result
        negative = result["negative_control"]
        self.assertTrue(negative["structural_match_is_not_badness"])
        self.assertEqual(negative["productive_repetition_window_indices"], [1])
        statuses = [item["status"] for item in result["held_out_C"]["evaluations"]]
        self.assertEqual(statuses, ["SURVIVED", "FALSIFIED", "SURVIVED", "NOT_MATCHED"])

    def test_gate_closes_transfer_only_and_products_remain_unimplemented(self):
        result = self.result
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertFalse(result["gate"]["phase5_started"])
        self.assertFalse(result["gate"]["product_implementation_started"])
        self.assertEqual(
            result["no_products_implemented"],
            ["CODEINE", "X-ANA-X", "VIZZ", "KETAMINE"],
        )


if __name__ == "__main__":
    unittest.main()
