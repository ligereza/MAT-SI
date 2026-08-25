"""Geometry-only primitives for the VIZZ multi-monitor integration.

This module deliberately stops before camera calibration, eye tracking,
machine learning, or clinical refraction.  It receives a calibrated 3-D gaze
ray and calibrated physical monitor planes, then computes screen hits and
physical viewing demand.  A caller must keep uncertainty and authority in its
own contract; a geometric hit is not a certified human-vision claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


EPSILON = 1e-9


@dataclass(frozen=True)
class Vec3:
    """Small dependency-free 3-D vector used by the geometry kernel."""

    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> "Vec3":
        return self * scalar

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def norm(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        length = self.norm()
        if length <= EPSILON:
            raise ValueError("cannot normalize a zero-length vector")
        return self * (1.0 / length)


@dataclass(frozen=True)
class GazeRay:
    """A calibrated gaze ray in one common world coordinate system."""

    origin: Vec3
    direction: Vec3

    def __post_init__(self) -> None:
        if self.direction.norm() <= EPSILON:
            raise ValueError("gaze direction must be non-zero")

    @property
    def unit_direction(self) -> Vec3:
        return self.direction.normalized()


@dataclass(frozen=True)
class ScreenPlane:
    """A physical rectangular monitor plane in world coordinates.

    ``origin`` is the top-left corner.  ``horizontal`` points toward the
    top-right corner and ``vertical`` points toward the bottom-left corner.
    The two basis vectors may be any non-zero orthogonal vectors; they are
    normalized for projection.
    """

    screen_id: str
    origin: Vec3
    horizontal: Vec3
    vertical: Vec3
    width_m: float
    height_m: float

    def __post_init__(self) -> None:
        if not self.screen_id:
            raise ValueError("screen_id must be non-empty")
        if self.width_m <= 0 or self.height_m <= 0:
            raise ValueError("screen dimensions must be positive")
        horizontal = self.horizontal.normalized()
        vertical = self.vertical.normalized()
        if abs(horizontal.dot(vertical)) > 1e-6:
            raise ValueError("screen basis vectors must be orthogonal")

    @property
    def horizontal_unit(self) -> Vec3:
        return self.horizontal.normalized()

    @property
    def vertical_unit(self) -> Vec3:
        return self.vertical.normalized()

    @property
    def normal(self) -> Vec3:
        return self.horizontal_unit.cross(self.vertical_unit).normalized()

    @classmethod
    def from_corners(
        cls,
        screen_id: str,
        top_left: Vec3,
        top_right: Vec3,
        bottom_left: Vec3,
    ) -> "ScreenPlane":
        """Build a plane from three measured physical corners."""

        horizontal = top_right - top_left
        vertical = bottom_left - top_left
        return cls(
            screen_id=screen_id,
            origin=top_left,
            horizontal=horizontal,
            vertical=vertical,
            width_m=horizontal.norm(),
            height_m=vertical.norm(),
        )

    def normalized_coordinates(self, point: Vec3) -> tuple[float, float]:
        relative = point - self.origin
        x_m = relative.dot(self.horizontal_unit)
        y_m = relative.dot(self.vertical_unit)
        return x_m / self.width_m, y_m / self.height_m


@dataclass(frozen=True)
class ScreenHit:
    """Intersection of a gaze ray with a visible point on a screen."""

    screen_id: str
    point: Vec3
    x_norm: float
    y_norm: float
    distance_m: float
    diopters: float


def diopters_from_distance(distance_m: float) -> float:
    """Return optical demand in diopters for a positive distance in metres."""

    if distance_m <= 0:
        raise ValueError("distance must be positive")
    return 1.0 / distance_m


def intersect_ray_with_screen(
    ray: GazeRay,
    screen: ScreenPlane,
    *,
    bounds_tolerance: float = 1e-9,
) -> ScreenHit | None:
    """Intersect a gaze ray with a screen rectangle.

    ``None`` means that the ray is parallel to the plane, points away from it,
    or intersects outside the physical rectangle.  This is geometry only; the
    caller must decide whether an absent hit is ``UNKNOWN`` under its evidence
    contract.
    """

    direction = ray.unit_direction
    normal = screen.normal
    denominator = direction.dot(normal)
    if abs(denominator) <= EPSILON:
        return None

    distance = (screen.origin - ray.origin).dot(normal) / denominator
    if distance <= EPSILON:
        return None

    point = ray.origin + direction * distance
    x_norm, y_norm = screen.normalized_coordinates(point)
    if (
        x_norm < -bounds_tolerance
        or x_norm > 1.0 + bounds_tolerance
        or y_norm < -bounds_tolerance
        or y_norm > 1.0 + bounds_tolerance
    ):
        return None

    x_norm = min(1.0, max(0.0, x_norm))
    y_norm = min(1.0, max(0.0, y_norm))
    return ScreenHit(
        screen_id=screen.screen_id,
        point=point,
        x_norm=x_norm,
        y_norm=y_norm,
        distance_m=distance,
        diopters=diopters_from_distance(distance),
    )


def intersect_all_screens(
    ray: GazeRay,
    screens: Iterable[ScreenPlane],
) -> tuple[ScreenHit, ...]:
    """Return valid screen hits ordered from nearest to farthest."""

    hits = [
        hit
        for screen in screens
        if (hit := intersect_ray_with_screen(ray, screen)) is not None
    ]
    return tuple(sorted(hits, key=lambda hit: hit.distance_m))


def screen_normal_angle(first: ScreenPlane, second: ScreenPlane) -> float:
    """Return the angle between two screen normals in radians."""

    cosine = first.normal.dot(second.normal)
    cosine = min(1.0, max(-1.0, cosine))
    return math.acos(cosine)
