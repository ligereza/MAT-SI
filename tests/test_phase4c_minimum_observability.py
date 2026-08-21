import unittest

from matsi.minimum_observability import run_phase4c


class Phase4CMinimumObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_phase4c()

    def test_frozen_sources_and_two_system_mappings(self):
        result = self.result
        self.assertEqual(result["parent_commit"], "6df7498")
        self.assertEqual(set(result["system_mapping"]), {"MAT-SI", "VIBECODEINE"})
        self.assertEqual(result["system_mapping"]["MAT-SI"]["raw_record_count"], 3)
        self.assertEqual(result["system_mapping"]["VIBECODEINE"]["raw_record_count"], 42)
        self.assertEqual(result["system_mapping"]["VIBECODEINE"]["usable_record_count"], 40)
        self.assertEqual(result["validation"]["record_count"], 43)

    def test_minimum_contract_is_complete_without_semantic_labels(self):
        result = self.result
        self.assertEqual(
            result["minimal_record"]["mandatory_fields"],
            ["before", "intervention", "after", "provenance"],
        )
        self.assertEqual(result["minimal_record"]["optional_fields"], ["resources"])
        self.assertTrue(result["validation"]["all_mandatory_fields_present"])
        self.assertTrue(result["validation"]["all_field_audits_complete"])
        self.assertTrue(result["validation"]["no_success_labels"])
        self.assertTrue(result["validation"]["resources_valid_vectors"])
        for summary in result["system_mapping"].values():
            self.assertTrue(summary["mandatory_contract_valid_for_all_usable_records"])

    def test_each_mandatory_field_has_a_falsifying_pair(self):
        pairs = self.result["counterexamples"]["mandatory_field_pairs"]
        self.assertEqual(set(pairs), {"before", "intervention", "after", "provenance"})
        for pair in pairs.values():
            self.assertTrue(pair["projection_equal_without_field"])
            self.assertTrue(pair["full_records_differ"])

    def test_resources_are_not_collapsed_and_missing_values_are_not_invented(self):
        result = self.result
        self.assertFalse(result["counterexamples"]["resource_vector_counterexample"].get("scalar_collapsed", False))
        self.assertTrue(result["minimal_record"]["scalar_cost_assumed"] is False)
        self.assertFalse(result["system_mapping"]["VIBECODEINE"]["resource_vector_available"])
        self.assertTrue(result["system_mapping"]["MAT-SI"]["resource_vector_available"])
        self.assertEqual(len(result["adapters"]["VIBECODEINE"]["unavailable_after"]), 2)

    def test_self_application_emits_the_same_contract(self):
        self_application = self.result["self_application"]
        self.assertTrue(self_application["same_record_contract"])
        self.assertTrue(self_application["existing_output_sufficient"])
        self.assertFalse(self_application["new_instrumentation_required"])
        self.assertEqual(self_application["records_emitted"], 3)

    def test_storage_is_transport_only_and_gate_is_phase4c(self):
        result = self.result
        self.assertTrue(result["storage_semantically_irrelevant"]["result"])
        self.assertEqual(result["gate"]["decision"], "A")
        self.assertFalse(result["gate"]["phase5_started"])
        self.assertFalse(result["gate"]["new_product_implementation_started"])


if __name__ == "__main__":
    unittest.main()
