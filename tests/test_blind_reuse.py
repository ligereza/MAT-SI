import json
import unittest

from matsi.blind_reuse import (
    DOMAINS,
    HELDOUT_DOMAIN,
    RESOURCE_KEYS,
    SIZE_LEVELS,
    STREAMS_PER_STRUCTURE,
    STRUCTURES_PER_SIZE,
    BlindPolicy,
    build_report,
    build_structures,
    iter_segments,
    _make_stream,
    _proposal,
    _render_raw,
)


class BlindReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report()

    def test_scale_is_larger_than_closure_accessibility_and_manifest_is_frozen(self):
        manifest = self.report["scale_manifest"]
        self.assertEqual(manifest["size_levels"], list(SIZE_LEVELS))
        self.assertEqual(len(SIZE_LEVELS), 6)
        self.assertEqual(manifest["structures_per_domain_size"], STRUCTURES_PER_SIZE)
        self.assertEqual(manifest["streams_per_structure"], STREAMS_PER_STRUCTURE)
        self.assertEqual(manifest["total_structures"], 600)
        self.assertEqual(manifest["total_streams"], 6000)
        self.assertGreater(manifest["total_events"], 1_000_000)

    def test_solver_facing_raw_object_has_no_labels_ids_or_future_length(self):
        structure = next(item for item in build_structures() if item.domain == "SUBSET_SUM" and item.size == 64)
        segment = next(iter(iter_segments(_make_stream(structure, 0))))
        forbidden = {"domain", "family", "case_name", "path", "structure_id", "hash", "stream_length"}
        self.assertTrue(forbidden.isdisjoint(segment.raw_object))
        policy = BlindPolicy()
        policy.start_stream()
        decision = policy.process(segment.raw_object, (0, 0))
        self.assertTrue(decision.prediction.startswith("KSTAR_INTERVAL=["))
        self.assertNotIn("future_length", policy.__dict__)

    def test_nuisance_serialization_preserves_coarse_signature_without_identity_hash(self):
        structure = next(item for item in build_structures() if item.domain == "SUBSET_SUM" and item.size == 64)
        raw_a = _render_raw(structure.domain, structure.payload, structure.size, 11)
        raw_b = _render_raw(structure.domain, structure.payload, structure.size, 29)
        proposal_a = _proposal(raw_a)
        proposal_b = _proposal(raw_b)
        self.assertNotEqual(repr(raw_a), repr(raw_b))
        self.assertEqual(proposal_a.signature, proposal_b.signature)
        self.assertEqual(proposal_a.identity, proposal_b.identity)
        self.assertFalse(hasattr(proposal_a, "stable_structure_id"))

    def test_heldout_automaton_is_raw_to_blind_policy(self):
        structure = next(item for item in build_structures() if item.domain == HELDOUT_DOMAIN and item.size == 64)
        segment = next(iter(iter_segments(_make_stream(structure, 0))))
        self.assertIsNone(_proposal(segment.raw_object))
        policy = BlindPolicy()
        policy.start_stream()
        decision = policy.process(segment.raw_object, (0, 0))
        self.assertEqual(decision.actions, ["RAW"])
        self.assertEqual(decision.prediction, "NO_REUSE_EXPECTED")

    def test_all_costs_keep_the_required_vector(self):
        for domain_result in self.report["domain_results"].values():
            for cost in domain_result["costs"].values():
                self.assertEqual(set(cost), set(RESOURCE_KEYS))
        for cost in self.report["blind_grouping_costs"].values():
            if isinstance(cost, dict) and set(cost).issuperset(RESOURCE_KEYS):
                self.assertEqual(set(cost), set(RESOURCE_KEYS))

    def test_baselines_are_exact_and_blind_errors_are_retained(self):
        for domain, result in self.report["domain_results"].items():
            for policy in ("B0_RAW", "B1_ORACLE_GROUPING", "B2_HASH_IDENTITY", "B3_SIMPLE_PAYBACK", "B4_DOMAIN_SPECIALIST"):
                self.assertEqual(result["answer_correctness"][policy]["accuracy"], 1.0, domain)
        stale = sum(result["stale_reuse_errors"] for result in self.report["domain_results"].values())
        self.assertGreater(stale, 0)
        self.assertGreater(self.report["grouping_metrics"]["false_merge_rate"], 0)

    def test_gates_and_break_even_are_not_overclaimed(self):
        gates = self.report["gates"]
        self.assertTrue(gates["DIES_BOOKKEEPING_ONLY"])
        self.assertTrue(gates["DIES_GROUPING_ORACLE"])
        self.assertTrue(gates["DIES_FALSE_MERGES"])
        self.assertFalse(gates["SURVIVES_WITHIN_DOMAIN"])
        self.assertFalse(gates["SURVIVES_HELDOUT_STRUCTURE"])
        self.assertFalse(gates["SURVIVES_HELDOUT_DOMAIN"])
        self.assertFalse(gates["STRONG_SURVIVAL"])
        calibration = self.report["break_even_calibration"]
        self.assertGreaterEqual(calibration["coverage"], 0.8)
        self.assertLessEqual(calibration["median_multiplicative_width"], 4.0)
        self.assertFalse(calibration["future_stream_length_was_input"])

    def test_heldout_domain_has_no_blind_gain(self):
        heldout = self.report["domain_results"][HELDOUT_DOMAIN]
        self.assertFalse(heldout["blind_componentwise_beats_raw"])
        self.assertEqual(heldout["answer_correctness"]["B5_BLIND_POLICY"]["accuracy"], 1.0)
        self.assertEqual(heldout["blind_minus_raw_component_delta"]["S"], 0)

    def test_replay_contract_separates_machine_metadata(self):
        replay = self.report["portability_and_replay"]
        self.assertIn("W in each cost vector", replay["machine_dependent_fields"])
        self.assertIn("machine_metadata", replay["machine_dependent_fields"])
        self.assertIn("W", self.report["domain_results"][DOMAINS[0]]["costs"]["B5_BLIND_POLICY"])
        self.assertIn("runtime_wall_ms", self.report["machine_metadata"])


if __name__ == "__main__":
    unittest.main()
