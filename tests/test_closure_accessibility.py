import copy
import json
import unittest

from matsi.closure_accessibility import (
    DISCOVERY_OBSERVATIONS,
    HELD_OUT_R,
    METHODS,
    PARENT_COMMIT,
    SCALAR_OBSERVATION_BUDGET,
    TRAIN_R,
    build_cases,
    build_report,
    fixed_scalar_observable,
    run_method,
)


class ClosureAccessibilityTests(unittest.TestCase):
    def test_same_order_families_have_distinct_raw_instances(self):
        cases = build_cases()
        by_r = {}
        for case in cases:
            by_r.setdefault(case.r_hidden, {})[case.family] = case
        for r in TRAIN_R + HELD_OUT_R:
            group = by_r[r]
            self.assertEqual(group["CANONICAL_CYCLE"].actual_global_order, r)
            self.assertEqual(group["CONJUGATED_CYCLE"].actual_global_order, r)
            self.assertEqual(group["RANDOM_SINGLE_CYCLE"].actual_global_order, r)
            self.assertEqual(
                len(
                    {
                        group["CANONICAL_CYCLE"].raw_instance_digest,
                        group["CONJUGATED_CYCLE"].raw_instance_digest,
                        group["RANDOM_SINGLE_CYCLE"].raw_instance_digest,
                    }
                ),
                3,
            )

    def test_multi_cycle_control_separates_orbit_from_global_order(self):
        controls = [case for case in build_cases() if case.family == "MULTI_CYCLE_CONTROL"]
        self.assertTrue(all(case.actual_global_order != case.r_hidden for case in controls))
        for case in controls:
            result = run_method(case, "STEP_ORACLE", "SEQUENTIAL_RETURN")
            self.assertEqual(result["status"], "EXACT")
            self.assertEqual(result["order_scope"], "start_orbit")
            self.assertNotEqual(result["order_estimate"], case.actual_global_order)

    def test_decoder_input_excludes_hidden_order_and_family(self):
        report = build_report()
        for case in report["cases"]:
            self.assertFalse(case["decoder_received_hidden_r"])
            self.assertFalse(case["decoder_received_family"])
            self.assertNotIn("r_hidden_oracle", case["decoder_input_fields"])
            self.assertNotIn("family", case["decoder_input_fields"])

    def test_resource_vector_is_not_collapsed_and_matrix_cost_is_counted(self):
        report = build_report()
        keys = set("QPMGDWC")
        for case in report["cases"]:
            for method in case["methods"]:
                self.assertEqual(set(method["resources"]), keys)
        matrix = run_method(
            next(case for case in build_cases() if case.family == "CANONICAL_CYCLE" and case.r_hidden == 5),
            "FULL_PERMUTATION_MATRIX",
            "EIGENSPECTRUM_FULL_MATRIX",
        )
        self.assertEqual(matrix["status"], "EXACT_REPRESENTATION_EXPENSIVE")
        self.assertEqual(matrix["resources"]["G"], matrix["resources"]["M"])
        self.assertGreater(matrix["resources"]["G"], 5)

    def test_fixed_scalar_has_no_order_descriptor(self):
        self.assertEqual(fixed_scalar_observable(0), 7)
        self.assertEqual(fixed_scalar_observable(1), 11)
        self.assertNotIn("r", fixed_scalar_observable.__code__.co_varnames)

    def test_frozen_parameters_and_gate_findings(self):
        report = build_report()
        self.assertEqual(report["parent_commit_actual"], PARENT_COMMIT)
        self.assertEqual(report["parameters_frozen_before_heldout"]["discovery_observations"], DISCOVERY_OBSERVATIONS)
        self.assertEqual(report["parameters_frozen_before_heldout"]["scalar_observation_budget"], SCALAR_OBSERVATION_BUDGET)
        self.assertEqual(report["parameters_frozen_before_heldout"]["train_r"], list(TRAIN_R))
        self.assertEqual(report["parameters_frozen_before_heldout"]["held_out_r"], list(HELD_OUT_R))
        self.assertTrue(report["gates"]["DIES_REPRESENTATION_LEAK"])
        self.assertTrue(report["gates"]["DIES_ENCODING_COST"])
        self.assertFalse(report["gates"]["SURVIVES_FAMILY_SPECIFIC"])
        self.assertFalse(report["gates"]["SURVIVES_CROSS_REPRESENTATION"])
        self.assertFalse(report["gates"]["STRONG_SURVIVAL"])

    def test_report_replay_is_deterministic_except_wall(self):
        first = build_report()
        second = build_report()

        def without_wall(value):
            if isinstance(value, dict):
                return {key: without_wall(item) for key, item in value.items() if key not in {"W", "wall_ms"}}
            if isinstance(value, list):
                return [without_wall(item) for item in value]
            return value

        self.assertEqual(without_wall(first), without_wall(second))
        self.assertEqual(json.dumps(without_wall(first), sort_keys=True), json.dumps(without_wall(second), sort_keys=True))

    def test_no_synthetic_phase_hash_is_used(self):
        report = build_report()
        self.assertEqual(report["leak_control"]["counts_as_main_evidence"], False)
        for case in report["cases"]:
            self.assertRegex(case["raw_instance_digest"], r"^[0-9a-f]{64}$")
            for method in case["methods"]:
                self.assertNotIn("phase", method)


if __name__ == "__main__":
    unittest.main()
