import unittest

from matsi.regime_economics import (
    JointCostScenario,
    audit_finite_joint_domain_coverage,
    audit_omitted_scenario_challenges,
    enumerate_finite_joint_cost_domain,
    evaluate_joint_cost_scenarios,
)


class JointCoverageTests(unittest.TestCase):
    def test_omitted_negative_scenario_falsifies_identify_certificate(self):
        declared = (
            JointCostScenario("a", 10, 6, 0),
            JointCostScenario("b", 10, 0, 9),
        )
        result = audit_omitted_scenario_challenges(
            declared,
            (JointCostScenario("omitted", 10, 9, 2),),
        )
        self.assertEqual(result["status"], "CERTIFICATE_FALSIFIED_BY_OMITTED_SCENARIO")
        self.assertTrue(result["attacks"][0]["falsifies_declared_certificate"])
        self.assertEqual(result["attacks"][0]["combined_decision"], "ABSTAIN_JOINT_UNCERTAIN")

    def test_omitted_positive_scenario_falsifies_direct_certificate(self):
        declared = (
            JointCostScenario("tie", 10, 5, 5),
            JointCostScenario("loss", 10, 8, 3),
        )
        self.assertEqual(evaluate_joint_cost_scenarios(declared)["decision"], "DIRECT_CERTIFIED")
        result = audit_omitted_scenario_challenges(
            declared,
            (JointCostScenario("omitted-positive", 10, 0, 0),),
        )
        self.assertEqual(result["status"], "CERTIFICATE_FALSIFIED_BY_OMITTED_SCENARIO")

    def test_surviving_a_challenger_is_not_a_completeness_proof(self):
        declared = (
            JointCostScenario("a", 10, 6, 0),
            JointCostScenario("b", 10, 0, 9),
        )
        result = audit_omitted_scenario_challenges(
            declared,
            (JointCostScenario("same-sign", 10, 4, 0),),
        )
        self.assertEqual(result["status"], "CERTIFICATE_SURVIVES_CHALLENGERS_NOT_COMPLETENESS_PROOF")

    def test_explicit_finite_domain_can_certify_coverage(self):
        domain = enumerate_finite_joint_cost_domain((10,), (6, 0), (0, 1))
        result = audit_finite_joint_domain_coverage(domain, domain)
        self.assertEqual(result["status"], "COVERAGE_COMPLETE_FOR_DECLARED_FINITE_DOMAIN")
        self.assertEqual(result["full_domain_decision"], "ROBUST_IDENTIFY_AND_SOLVE")
        self.assertEqual(result["missing_scenarios"], [])

    def test_partial_finite_domain_is_explicitly_incomplete(self):
        domain = enumerate_finite_joint_cost_domain((10,), (6, 0), (0, 1))
        result = audit_finite_joint_domain_coverage(domain[:2], domain)
        self.assertEqual(result["status"], "COVERAGE_INCOMPLETE_FOR_DECLARED_FINITE_DOMAIN")
        self.assertEqual(len(result["missing_scenarios"]), 2)

    def test_domain_axes_must_be_nonempty(self):
        with self.assertRaises(ValueError):
            enumerate_finite_joint_cost_domain((), (1,), (1,))


if __name__ == "__main__":
    unittest.main()

