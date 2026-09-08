"""Tests prepared for PREDICAR; intentionally not executed during setup."""

import unittest

from predicar.bootstrap import INITIAL_SPEC, preparation_plan, research_area_ids
from predicar.spec import BinaryState


class PredicarContractTests(unittest.TestCase):
    def test_initial_spec_is_exact_cardinality(self):
        state = BinaryState.from_indices(range(14), INITIAL_SPEC)
        state.validate(INITIAL_SPEC)

    def test_preparation_plan_has_no_folds_yet(self):
        plan = preparation_plan()
        self.assertEqual(plan.protocol_id, "predicar-v0")
        self.assertEqual(plan.folds, ())
        self.assertFalse(plan.spec is None)

    def test_six_research_areas_are_registered(self):
        self.assertEqual(
            research_area_ids(),
            (
                "rfs_tracking",
                "neural_population",
                "statistical_physics",
                "error_correcting",
                "point_processes",
                "constraint_programming",
            ),
        )
