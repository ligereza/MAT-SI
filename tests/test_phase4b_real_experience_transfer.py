import unittest

from matsi.real_experience_transfer import run_phase4b


class Phase4BRealExperienceTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase4b()

    def test_real_manifest_and_adapters_use_only_preexisting_evidence(self):
        result = self.result
        self.assertTrue(result["raw_sources_only"])
        self.assertEqual(result["raw_manifest_commit"], "7a2ebb2")
        self.assertEqual(result["adapters"]["A"]["event_count"], 13)
        self.assertEqual(result["adapters"]["B"]["event_count"], 42)
        for adapter in result["adapters"].values():
            audit = adapter["audit"]
            self.assertTrue(audit["PRESERVED"])
            self.assertTrue(audit["NORMALIZED"])
            self.assertTrue(audit["LOST"])
            self.assertTrue(audit["RESIDUE"])
            self.assertTrue(audit["derived_fields"])

    def test_missing_behavior_fields_are_not_invented(self):
        discovery = self.result["discovery_from_A_B"]
        self.assertEqual(discovery["status"], "NO_COMPARABLE_BEHAVIORAL_RELATION")
        self.assertEqual(discovery["candidate_relations"], [])
        self.assertEqual(
            discovery["behavior_field_availability"],
            {"action": False, "outcome": False, "cost": False},
        )
        self.assertEqual(discovery["comparable_behavior_fields"], [])
        self.assertGreater(discovery["generic_relation_attempt_count"], 0)
        self.assertFalse(self.result["common_envelope"]["semantics_invented"])
        self.assertFalse(self.result["common_envelope"]["envelope_is_imposing_the_pattern"])

    def test_held_out_C_is_not_claimed_after_pre_freeze_inspection(self):
        held_out = self.result["held_out_C"]
        self.assertFalse(held_out["loaded"])
        self.assertTrue(held_out["selection_frozen"])
        self.assertTrue(held_out["pre_freeze_header_inspected"])
        self.assertIn("invalidated", held_out["evaluation_contamination"])

    def test_gate_reports_observability_bottleneck_and_no_products(self):
        result = self.result
        self.assertEqual(result["gate"]["decision"], "B")
        self.assertFalse(result["gate"]["phase5_started"])
        self.assertFalse(result["gate"]["product_implementation_started"])


if __name__ == "__main__":
    unittest.main()
