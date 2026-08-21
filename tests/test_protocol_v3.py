import unittest

from matsi.axis_experiments import DirectEvaluator, ReducedRewriteEvaluator, RewriteEvaluator
from matsi.continuity import continuity_cases, run_continuity_analysis
from matsi.kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from matsi.rule_experiments import run_rule_control, run_transformation_universe


class ProtocolV3Tests(unittest.TestCase):
    def setUp(self):
        self.kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]

    def test_separated_evaluators_work_over_both_structural_substrates(self):
        substrates = [AtomPairKernel(), ContentDagKernel()]
        evaluators = [DirectEvaluator(), RewriteEvaluator(), ReducedRewriteEvaluator()]
        for substrate in substrates:
            representation = substrate.encode([1, 2, 3])
            for evaluator in evaluators:
                result = evaluator.evaluate(substrate, representation, "double_reverse")
                self.assertEqual(substrate.decode(result.representation), [1, 2, 3], evaluator.name)

    def test_represented_rule_changes_execution_and_self_modifies(self):
        result = run_rule_control(self.kernels)
        self.assertTrue(result["all_pass"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertTrue(all(row["same_evaluator_source_hash"] for row in result["rows"]))

    def test_transformations_history_cost_and_provenance_are_ordinary_data(self):
        result = run_transformation_universe(self.kernels)
        self.assertTrue(result["all_pass"])
        self.assertEqual(result["rows"][0]["composition_result"], {"value": 8})

    def test_continuity_uses_relations_without_stable_id(self):
        result = run_continuity_analysis(self.kernels)
        self.assertEqual(len(result["cases"]), 9)
        self.assertTrue(all(row["round_trip"] for row in result["rows"]))
        self.assertTrue(all(not row["facts"]["stable_id_field_present"] for row in result["rows"]))
        convergence = [row for row in result["rows"] if row["case_id"] == "independent_convergence"]
        self.assertTrue(all(row["facts"]["content_equal"] for row in convergence))
        self.assertTrue(all(not row["facts"]["historical_path_available"] for row in convergence))


if __name__ == "__main__":
    unittest.main()
