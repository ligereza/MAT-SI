import unittest

from matsi.continuity_policy import run_continuity_policy_trial
from matsi.fair_egraph import run_fair_egraph_trial
from matsi.held_out import run_held_out
from matsi.kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from matsi.minimal_rewrite import run_minimum_core_trial


class ProtocolV4Tests(unittest.TestCase):
    def setUp(self):
        self.kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]

    def test_generic_rules_control_multiple_behaviors_without_branches(self):
        result = run_minimum_core_trial(self.kernels)
        self.assertTrue(result["all_pass"])
        self.assertEqual(result["behavior_specific_python_branches"], 0)
        self.assertTrue(result["same_core_source_hash"])

    def test_fair_egraph_workload_exposes_shared_alternatives(self):
        result = run_fair_egraph_trial()
        self.assertTrue(result["tree_order_changes_result"])
        self.assertTrue(result["egraph_order_invariant"])
        self.assertTrue(result["egraph_has_structural_advantage"])
        self.assertTrue(all(row["egraph_recovers_lowest_cost"] for row in result["rows"]))

    def test_same_history_supports_two_continuity_policies(self):
        result = run_continuity_policy_trial(self.kernels)
        self.assertTrue(result["same_history_under_both_policies"])
        self.assertTrue(result["claims_coexist_over_same_evidence"])
        self.assertTrue(result["claims_preserve_provenance"])
        self.assertFalse(result["stable_identity_primitive_used"])

    def test_frozen_held_out_corpus_executes_represented_novel_behavior(self):
        result = run_held_out(self.kernels)
        self.assertTrue(result["representation_survives"])
        self.assertFalse(result["semantic_core_modified"])
        self.assertTrue(result["represented_definitions_execute"])
        self.assertTrue(result["all_programs_use_only_fixed_vm_ops"])
        self.assertTrue(result["host_source_unchanged"])
        self.assertFalse(result["unexpected_evaluation_failures"])


if __name__ == "__main__":
    unittest.main()
