import unittest

from matsi.canonical import apply_operation, get_path
from matsi.corpus import load_corpus
from matsi.kernels import AtomPairKernel, ContentDagKernel, RewriteEgraphKernel


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.corpus = load_corpus()
        self.kernels = [AtomPairKernel(), ContentDagKernel(), RewriteEgraphKernel()]

    def test_every_candidate_round_trips_every_case(self):
        for kernel in self.kernels:
            for case in self.corpus:
                value = kernel.self_description() if case["id"] == "self_model_request" else case["value"]
                self.assertEqual(kernel.decode(kernel.encode(value)), value, (kernel.name, case["id"]))

    def test_every_candidate_applies_the_same_transformations(self):
        for kernel in self.kernels:
            for case in self.corpus:
                if case["id"] == "self_model_request":
                    value = kernel.self_description()
                    operation = "identity"
                    source = value["primitives"]
                else:
                    value = case["value"]
                    operation = case["transform"]["operation"]
                    source = get_path(value, case["transform"]["source_path"])
                result = kernel.transform(kernel.encode(source), operation)
                self.assertEqual(kernel.decode(result.representation), apply_operation(source, operation))

    def test_lossy_residue_is_explicit_data(self):
        case = next(item for item in self.corpus if item["id"] == "lossy_transformation")
        self.assertEqual(case["value"]["result"], apply_operation(case["value"]["source"], "lowercase"))
        self.assertIn("residue", case["value"])

    def test_egraph_performs_a_rewrite_merge(self):
        kernel = RewriteEgraphKernel()
        result = kernel.transform(kernel.encode([1, 2, 3]), "reverse")
        self.assertEqual(kernel.decode(result.representation), [3, 2, 1])
        self.assertGreater(result.cost, 0)
