import unittest

from matsi.real_distillation import run_phase3b


class Phase3BRealDistillationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase3b()

    def test_manifest_is_frozen_before_real_analysis(self):
        result = self.result
        self.assertEqual(result["manifest_commit"], "4e8921c")
        self.assertEqual(
            {entry["assignment"] for entry in result["manifest"]["entries"]},
            {"discovery_A", "discovery_B", "held_out_C", "negative_control_N1", "negative_control_N2"},
        )

    def test_adapter_audits_preserved_normalized_and_lost_information(self):
        for audit in self.result["adapter_audit"].values():
            self.assertTrue(audit["preserves"])
            self.assertTrue(audit["normalizes"])
            self.assertTrue(audit["loses_or_excludes"])
            self.assertTrue(audit["lost_information_residue_present"])

    def test_real_discovery_is_structural_but_not_semantically_trusted(self):
        selected = self.result["blind_structural_pass"]["discovery"]["selected_G"]
        self.assertGreater(selected["compression_gain"], 0)
        self.assertTrue(selected["reconstruction_left"])
        self.assertTrue(selected["reconstruction_right"])
        self.assertEqual(selected["semantic_status"], "unavailable")
        self.assertFalse(selected["static_behavior_equal"])

    def test_negative_controls_expose_false_abstractions_and_close_gate(self):
        negatives = self.result["blind_structural_pass"]["negative_controls"]
        self.assertTrue(all(item["useful_value"] for item in negatives.values()))
        self.assertFalse(self.result["gate_answers"]["negative_controls_rejected"])
        self.assertEqual(self.result["gate"]["decision"], "C")
        self.assertFalse(self.result["gate"]["full_repository_ingestion_started"])
        self.assertFalse(self.result["gate"]["phase4_started"])

    def test_held_out_and_surprise_are_recorded_without_claiming_success(self):
        held_out = self.result["blind_structural_pass"]["held_out_C"]
        self.assertFalse(held_out["participated_in_discovery"])
        self.assertTrue(held_out["G_frozen_before_evaluation"])
        self.assertTrue(self.result["surprise_test"]["surprising_structure_present"])
        self.assertEqual(
            self.result["representation_alignment"]["status"],
            "required_known_normalization",
        )


if __name__ == "__main__":
    unittest.main()
