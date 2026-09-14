"""High-level construction of polyhedral hypercube-graph surfaces."""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .config import DEFAULT_GEOMETRY_CONFIG, GeometryConfig
from .geometry import (
    apply_projective_transform,
    apply_z_shear,
    apply_z_shift,
    choose_vertical_cut,
    clip_with_xy_plane,
    cut_last_corner,
    normalize_height,
    reflect_surface,
)
from .model import Polygon3D


def create_base_surface() -> list[Polygon3D]:
    """Create the unit square representing the single-vertex graph Q_0."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
        ]
    )
    return [Polygon3D(vertices, label="poly_1")]


def perform_inductive_step(
    polygons: list[Polygon3D],
    *,
    config: GeometryConfig = DEFAULT_GEOMETRY_CONFIG,
) -> list[Polygon3D]:
    """Construct the next dimension, mutating existing polygon objects."""
    apply_z_shear(
        polygons,
        margin=config.shear_margin,
        tolerance=config.zero_tolerance,
    )
    apply_z_shift(polygons, tolerance=config.zero_tolerance)
    clip_with_xy_plane(polygons, tolerance=config.zero_tolerance)
    polygons = reflect_surface(polygons)
    a, b = choose_vertical_cut(
        polygons,
        fraction=config.cut_fraction,
        margin=config.cut_margin,
        tolerance=config.zero_tolerance,
    )
    cut_last_corner(polygons, a, b, tolerance=config.zero_tolerance)
    apply_projective_transform(
        polygons,
        a,
        b,
        tolerance=config.zero_tolerance,
    )
    normalize_height(
        polygons,
        target_height=config.target_height,
        tolerance=config.zero_tolerance,
    )
    for index, polygon in enumerate(polygons, start=1):
        polygon.label = f"poly_{index}"
    return polygons


def generate_hypercube_surface(
    dimension: int,
    *,
    config: GeometryConfig = DEFAULT_GEOMETRY_CONFIG,
) -> list[Polygon3D]:
    """Create a fresh surface for an integer dimension d >= 0."""
    if isinstance(dimension, (bool, np.bool_)) or not isinstance(dimension, Integral):
        raise TypeError("Die Dimension muss eine ganze Zahl sein; bool ist nicht zulässig.")
    if dimension < 0:
        raise ValueError("Die Dimension darf nicht negativ sein.")
    polygons = create_base_surface()
    for _ in range(int(dimension)):
        polygons = perform_inductive_step(polygons, config=config)
    return polygons


__all__ = [
    "create_base_surface",
    "generate_hypercube_surface",
    "perform_inductive_step",
]

