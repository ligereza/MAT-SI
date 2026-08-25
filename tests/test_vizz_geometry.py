"""Deterministic geometry checks for the VIZZ multi-monitor integration."""

from __future__ import annotations

import math
import unittest

from matsi.vizz_geometry import (
    GazeRay,
    ScreenPlane,
    Vec3,
    diopters_from_distance,
    intersect_all_screens,
    intersect_ray_with_screen,
    screen_normal_angle,
)


class VizzGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.front = ScreenPlane(
            "front",
            Vec3(-0.5, -0.3, 1.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 0.6, 0.0),
            1.0,
            0.6,
        )

    def test_ray_hit_returns_local_coordinates_and_diopters(self):
        ray = GazeRay(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))
        hit = intersect_ray_with_screen(ray, self.front)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.screen_id, "front")
        self.assertAlmostEqual(hit.x_norm, 0.5)
        self.assertAlmostEqual(hit.y_norm, 0.5)
        self.assertAlmostEqual(hit.distance_m, 1.0)
        self.assertAlmostEqual(hit.diopters, 1.0)

    def test_screen_can_be_oblique_to_the_gaze(self):
        screen = ScreenPlane.from_corners(
            "oblique",
            Vec3(0.0, -0.25, 1.0),
            Vec3(0.5, -0.25, 1.5),
            Vec3(0.0, 0.25, 1.0),
        )
        target = (
            screen.origin
            + screen.horizontal_unit * (screen.width_m * 0.5)
            + screen.vertical_unit * (screen.height_m * 0.5)
        )
        ray = GazeRay(Vec3(0.0, 0.0, 0.0), target)
        hit = intersect_ray_with_screen(ray, screen)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertAlmostEqual(hit.x_norm, 0.5)
        self.assertAlmostEqual(hit.y_norm, 0.5)

    def test_multiple_screens_are_selected_by_3d_intersection(self):
        left = ScreenPlane(
            "left",
            Vec3(-1.2, -0.3, 1.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 0.6, 0.0),
            1.0,
            0.6,
        )
        ray = GazeRay(Vec3(0.0, 0.0, 0.0), Vec3(-0.9, 0.0, 1.0))
        hits = intersect_all_screens(ray, (left, self.front))
        self.assertEqual([hit.screen_id for hit in hits], ["left"])

    def test_outside_screen_and_parallel_ray_are_not_hits(self):
        outside = GazeRay(Vec3(0.0, 0.0, 0.0), Vec3(2.0, 0.0, 1.0))
        parallel = GazeRay(Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
        self.assertIsNone(intersect_ray_with_screen(outside, self.front))
        self.assertIsNone(intersect_ray_with_screen(parallel, self.front))

    def test_diopters_and_screen_angle(self):
        self.assertAlmostEqual(diopters_from_distance(0.5), 2.0)
        side = ScreenPlane(
            "side",
            Vec3(1.0, -0.3, 0.0),
            Vec3(0.0, 0.0, 1.0),
            Vec3(0.0, 0.6, 0.0),
            1.0,
            0.6,
        )
        self.assertAlmostEqual(screen_normal_angle(self.front, side), math.pi / 2)

    def test_invalid_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            GazeRay(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            ScreenPlane("bad", Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(2.0, 0.0, 0.0), 1.0, 1.0)
