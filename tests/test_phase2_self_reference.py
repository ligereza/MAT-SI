import unittest

from matsi.self_reference import run_phase2


class Phase2SelfReferenceTests(unittest.TestCase):
    def test_self_reference_gate_passes_without_reopening_phase1(self):
        result = run_phase2()
        self.assertTrue(result["all_required_evidence"])
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertFalse(result["gate"]["phase3_started"])
        self.assertFalse(result["gate"]["phase1_assumption_broke"])

    def test_self_model_is_inspected_and_transformed_by_same_vm(self):
        result = run_phase2()
        for row in result["rows"]:
            self.assertTrue(row["self_model_distinguishes_description_and_executable"])
            self.assertTrue(row["inspection"]["reconstructs_exactly"])
            self.assertEqual(row["behavior_before"], 4)
            self.assertEqual(row["behavior_after"], 6)
            self.assertTrue(row["behavior_changed"])
            self.assertTrue(row["evaluator_source_unchanged"])
            self.assertTrue(row["same_external_self_mechanism"])
            self.assertTrue(row["history_round_trip"])

    def test_self_claims_and_failure_attacks_are_preserved(self):
        result = run_phase2()
        for row in result["rows"]:
            failures = row["failure_attacks"]
            self.assertTrue(row["correspondence_baseline_consistent"])
            self.assertTrue(failures["all_failures_preserved"])
            self.assertEqual(failures["corrupted_represented_rule"]["status"], "unknown")
            self.assertEqual(failures["claim_unsupported_by_provenance"]["status"], "unsupported")

    def test_self_evaluation_selects_claim_without_source_mutation(self):
        result = run_phase2()
        for row in result["rows"]:
            selection = row["self_evaluation"]
            self.assertTrue(selection["claim_round_trip"])
            self.assertTrue(selection["selects_lowest_cost"])
            self.assertFalse(selection["source_mutated"])
            self.assertEqual(
                [alternative["output"] for alternative in selection["alternatives"]],
                [4, 4],
            )


if __name__ == "__main__":
    unittest.main()
