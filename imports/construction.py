"""High-level construction of polyhedral hypercube-graph surfaces."""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .config import DEFAULT_GEOMETRY_CONFIG, GeometryConfig
from .geometry import (
    apply_projective_transform,
    apply_z_shear,
    apply_z_shift,
    clip_with_xy_plane,
    cut_last_corner,
    normalize_height,
    reflect_surface,
)
from .model import Polygon3D

UNIT_SQUARE = ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0))


def create_base_surface() -> list[Polygon3D]:
    """Create the unit square representing the single-vertex graph Q_0."""
    return [Polygon3D(UNIT_SQUARE, label="poly_1")]


def _next_surface(vertices: np.ndarray, config: GeometryConfig) -> np.ndarray:
    """One inductive step on the stacked array: (n, k, 3) → (2n, k + 1, 3)."""
    apply_z_shear(vertices, config)
    apply_z_shift(vertices, config)
    vertices = reflect_surface(clip_with_xy_plane(vertices, config))
    vertices, a, b = cut_last_corner(vertices, config)
    vertices = apply_projective_transform(vertices, a, b, config)
    normalize_height(vertices, config)
    return vertices


def perform_inductive_step(
    polygons: list[Polygon3D],
    *,
    config: GeometryConfig = DEFAULT_GEOMETRY_CONFIG,
) -> list[Polygon3D]:
    """Construct the next dimension, mutating existing polygon objects."""
    if not polygons:
        raise ValueError("Die Oberfläche darf nicht leer sein.")
    vertices = _next_surface(np.stack([polygon.vertices for polygon in polygons]), config)
    for polygon, polygon_vertices in zip(polygons, vertices):
        polygon.vertices = polygon_vertices
    polygons = polygons + [Polygon3D(v) for v in vertices[len(polygons):]]
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
    vertices = np.array([UNIT_SQUARE])
    for _ in range(int(dimension)):
        vertices = _next_surface(vertices, config)
    return [
        Polygon3D(polygon_vertices, label=f"poly_{index}")
        for index, polygon_vertices in enumerate(vertices, start=1)
    ]


__all__ = [
    "create_base_surface",
    "generate_hypercube_surface",
    "perform_inductive_step",
]
