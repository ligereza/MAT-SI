"""MAT-SI Phase 1 experimental kernel comparison."""

from .canonical import canonical_bytes, deep_node_count, get_path
from .corpus import load_corpus
from .vizz_geometry import (
    GazeRay,
    ScreenHit,
    ScreenPlane,
    Vec3,
    diopters_from_distance,
    intersect_all_screens,
    intersect_ray_with_screen,
    screen_normal_angle,
)

__all__ = [
    "GazeRay",
    "ScreenHit",
    "ScreenPlane",
    "Vec3",
    "canonical_bytes",
    "deep_node_count",
    "diopters_from_distance",
    "get_path",
    "intersect_all_screens",
    "intersect_ray_with_screen",
    "load_corpus",
    "screen_normal_angle",
]
