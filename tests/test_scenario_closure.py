import unittest

from matsi.scenario_closure import (
    AffineModeRule,
    audit_affine_mode_closure,
    run_scenario_closure_experiment,
)


class ScenarioClosureTests(unittest.TestCase):
    def setUp(self):
        self.rule = AffineModeRule(
            modes=(0, 1),
            direct_base=10,
            direct_step=0,
            downstream_base=6,
            downstream_step=-6,
            identification_base=0,
            identification_step=9,
        )

    def test_complete_generator_matches_independent_oracle(self):
        result = audit_affine_mode_closure(self.rule)
        self.assertEqual(result["closure_status"], "CLOSURE_MATCHED_FINITE_DOMAIN")
        self.assertEqual(result["generated_count"], 2)
        self.assertEqual(result["oracle_count"], 2)
        self.assertEqual(result["missing_from_generator"], [])
        self.assertEqual(result["extra_in_generator"], [])

    def test_complete_generator_has_end_to_end_advantage(self):
        result = audit_affine_mode_closure(self.rule)
        self.assertEqual(result["oracle_decision"], "ROBUST_IDENTIFY_AND_SOLVE")
        self.assertTrue(result["end_to_end_advantage"])
        self.assertEqual(result["oracle_min_net_gain"], "1")
        self.assertTrue(result["identification_cost_accounted"])

    def test_dropping_one_mode_falsifies_closure(self):
        result = audit_affine_mode_closure(self.rule, drop_modes=(1,))
        self.assertEqual(result["closure_status"], "CLOSURE_FALSIFIED")
        self.assertEqual(len(result["missing_from_generator"]), 1)
        self.assertEqual(result["missing_from_generator"][0]["id"], "oracle-mode-1")

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.rule.generate(drop_modes=(2,))

    def test_experiment_reports_bounded_gate(self):
        result = run_scenario_closure_experiment()
        self.assertEqual(result["gate"], "SUCCESS_WITHIN_FINITE_DECLARED_CLASS_ONLY")
        self.assertEqual(
            result["incomplete_negative_control"]["closure_status"],
            "CLOSURE_FALSIFIED",
        )


if __name__ == "__main__":
    unittest.main()

