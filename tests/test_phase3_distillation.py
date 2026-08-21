import unittest

from matsi.distillation import run_phase3


class Phase3DistillationTests(unittest.TestCase):
    def test_discovery_gate_passes_without_repository_ingestion(self):
        result = run_phase3()
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertTrue(result["gate_answers"]["derive_G_without_being_told"])
        self.assertTrue(result["gate_answers"]["reconstruct_A_B_from_G_residue"])
        self.assertFalse(result["full_repository_ingestion"])

    def test_generalization_keeps_structure_semantics_and_residue_separate(self):
        result = run_phase3()
        discovery = result["discovery_from_A_B"]
        candidate = discovery["candidate_G"]
        self.assertTrue(discovery["useful_abstraction"])
        self.assertTrue(candidate["reconstruction_left"])
        self.assertTrue(candidate["reconstruction_right"])
        self.assertTrue(candidate["semantic_equivalence"])
        self.assertGreater(candidate["compression_gain"], 0)
        self.assertTrue(candidate["residue_left"])
        self.assertTrue(candidate["residue_right"])
        self.assertFalse(discovery["baselines"]["exact_structural_matching"]["matches"])
        self.assertFalse(discovery["baselines"]["naive_subtree_recurrence"]["reconstructs_pair"])

    def test_negative_controls_reject_misleading_similarity(self):
        controls = run_phase3()["controlled_controls"]
        self.assertFalse(controls["similar_surface_different_behavior"]["useful_abstraction"])
        self.assertEqual(
            controls["similar_surface_different_behavior"]["rejection_reason"],
            "semantic_mismatch",
        )
        self.assertFalse(controls["no_useful_shared_abstraction"]["useful_abstraction"])
        self.assertTrue(controls["same_transformation_different_names"]["useful_abstraction"])

    def test_held_out_c_is_predicted_by_frozen_g(self):
        held_out = run_phase3()["held_out_C"]
        self.assertFalse(held_out["participated_in_discovery"])
        self.assertTrue(held_out["matches_G"])
        self.assertTrue(held_out["reconstruction"])
        self.assertTrue(held_out["predicts_property"])
        self.assertTrue(held_out["description_advantage"])
        self.assertLess(held_out["G_marginal_explanation_cost"], held_out["generic_baseline_cost"])

    def test_cross_representation_requires_represented_normalization(self):
        cross = run_phase3()["cross_representation"]
        self.assertTrue(cross["raw_layout_alone_would_fail"])
        self.assertTrue(cross["G_survives_surface_change_after_represented_normalization"])
        self.assertTrue(cross["normalized_surface"]["reconstructs_b"])
        self.assertTrue(cross["normalized_surface"]["semantic_equivalence"])


if __name__ == "__main__":
    unittest.main()
