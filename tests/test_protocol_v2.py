import unittest

from matsi.identity import identity_cases, run_identity_analysis
from matsi.kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel
from matsi.kernels.rewrite_egraph import Variable, _default_rules, _rewrite_root
from matsi.scale import scaled_cases, scale_manifest


class ProtocolV2Tests(unittest.TestCase):
    def setUp(self):
        self.kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]

    def test_scale_manifest_and_shapes(self):
        manifest = scale_manifest((10, 100))
        self.assertEqual(len(manifest), 6)
        self.assertEqual({item["shape"] for item in manifest}, {"repetition", "shared_graph", "temporal_branching"})
        cases = scaled_cases((10,))
        self.assertEqual({case["size"] for case in cases}, {10})

    def test_scaled_cases_round_trip_for_all_kernels(self):
        for kernel in self.kernels:
            for case in scaled_cases((10,)):
                representation = kernel.encode(case["value"])
                self.assertEqual(kernel.decode(representation), case["value"], (kernel.name, case["id"]))
                self.assertEqual(kernel.storage_breakdown(representation)["total_bytes"], kernel.size_bytes(representation))

    def test_self_application_is_observable(self):
        for kernel in self.kernels:
            result = kernel.self_application()
            self.assertTrue(result.model_round_trip, kernel.name)
            self.assertTrue(result.model_transform_ok, kernel.name)
            self.assertTrue(result.query_ok, kernel.name)
            self.assertTrue(result.transform_ok, kernel.name)

    def test_egraph_rule_is_variable_based_and_generic(self):
        rule = next(rule for rule in _default_rules() if rule.name == "idempotent_wrap")
        term = ("wrap", (("wrap", (("atom", ("1",)),)),))
        self.assertEqual(_rewrite_root(term, rule), ("wrap", (("atom", ("1",)),)))
        self.assertIsInstance(rule.lhs[1][0][1][0], Variable)

    def test_identity_attacks_remain_counterexamples(self):
        analysis = run_identity_analysis(self.kernels)
        self.assertEqual(len(analysis["cases"]), 4)
        observations = analysis["observations"]
        self.assertEqual(len(observations), 12)
        same_content = [row for row in observations if row["case_id"] == "same_content_different_name"]
        self.assertTrue(all(row["content_projection_equal"] for row in same_content))
        self.assertTrue(all(not row["annotation_projection_equal"] for row in same_content))


if __name__ == "__main__":
    unittest.main()
