import unittest

from matsi.frozen_source import SOURCE_AVAILABLE
from matsi.real_experience_transfer import run_phase4b


class Phase4BRealExperienceTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase4b()
        cls.available = {
            source_id
            for source_id, item in cls.result["source_resolution"].items()
            if item["status"] == SOURCE_AVAILABLE
        }
        cls.recomputable = {"A", "B"} <= cls.available

    def _require_private_sources(self):
        if not self.recomputable:
            self.skipTest(
                "Phase 4B derives from private local histories that are not committed; "
                "they are absent on this machine so the derivation is not reproduced here"
            )

    def test_real_manifest_and_adapters_use_only_preexisting_evidence(self):
        result = self.result
        self.assertTrue(result["raw_sources_only"])
        self.assertEqual(result["raw_manifest_commit"], "7a2ebb2")
        self._require_private_sources()
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
        self.assertFalse(self.result["common_envelope"]["semantics_invented"])
        self.assertFalse(self.result["common_envelope"]["envelope_is_imposing_the_pattern"])
        self._require_private_sources()
        discovery = self.result["discovery_from_A_B"]
        self.assertEqual(discovery["status"], "NO_COMPARABLE_BEHAVIORAL_RELATION")
        self.assertEqual(discovery["candidate_relations"], [])
        self.assertEqual(
            discovery["behavior_field_availability"],
            {"action": False, "outcome": False, "cost": False},
        )
        self.assertEqual(discovery["comparable_behavior_fields"], [])
        self.assertGreater(discovery["generic_relation_attempt_count"], 0)

    def test_absent_private_sources_do_not_fabricate_a_discovery(self):
        if self.recomputable:
            self.skipTest("private sources are present on this machine")
        discovery = self.result["discovery_from_A_B"]
        self.assertEqual(discovery["status"], "NOT_RECOMPUTED_WITHOUT_PRIVATE_SOURCES")
        self.assertIsNone(discovery["candidate_relations"])
        self.assertIsNone(discovery["behavior_field_availability"])
        self.assertEqual(discovery["missing_sources"], ["A", "B"])

    def test_held_out_C_is_not_claimed_after_pre_freeze_inspection(self):
        held_out = self.result["held_out_C"]
        self.assertFalse(held_out["loaded"])
        self.assertTrue(held_out["selection_frozen"])
        self.assertTrue(held_out["pre_freeze_header_inspected"])
        self.assertIn("invalidated", held_out["evaluation_contamination"])

    def test_held_out_C_is_never_even_probed(self):
        self.assertNotIn("C", self.result["source_resolution"])
        self.assertTrue(self.result["reproduction"]["held_out_C_not_probed"])

    def test_gate_reports_observability_bottleneck_and_no_products(self):
        gate = self.result["gate"]
        self.assertEqual(gate["historical_decision"], "B")
        self.assertFalse(gate["phase5_started"])
        self.assertFalse(gate["product_implementation_started"])
        if self.recomputable:
            self.assertEqual(gate["decision"], "B")
            self.assertTrue(gate["historical_decision_reproduced_here"])
        else:
            self.assertIsNone(gate["decision"])
            self.assertEqual(gate["status"], "REQUIRES_PRIVATE_SOURCES")
            self.assertFalse(gate["historical_decision_reproduced_here"])


if __name__ == "__main__":
    unittest.main()
