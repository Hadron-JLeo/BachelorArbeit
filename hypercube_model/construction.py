"""Induktive Konstruktion polyedrischer Hyperwürfeloberflächen."""

import numpy as np

from .geometry import (
    apply_projective_transform,
    choose_vertical_cut,
    clip_with_xy_plane,
    cut_last_corner,
    normalize_height,
    reflect_surface,
    shear_and_shift_surface,
)
from .models import Polygon3D


def create_base_surface() -> list[Polygon3D]:
    """Erzeugt das Einheitsquadrat als Darstellung von Q_0."""

    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
        ]
    )
    return [Polygon3D(vertices, label="poly_1")]


def perform_inductive_step(polygons: list[Polygon3D]) -> list[Polygon3D]:
    """Erzeugt aus einer Darstellung von Q_d eine Darstellung von Q_(d+1)."""

    if not polygons:
        raise ValueError("mindestens ein Polygon wird benötigt")

    result = [Polygon3D(polygon.vertices, polygon.label) for polygon in polygons]
    shear_and_shift_surface(result)
    clip_with_xy_plane(result)
    result = reflect_surface(result)
    a, b = choose_vertical_cut(result)
    cut_last_corner(result, a, b)
    apply_projective_transform(result, a, b)
    normalize_height(result)
    return result


def generate_hypercube_surface(dimension: int) -> list[Polygon3D]:
    """Erzeugt die polyedrische Oberfläche für Q_dimension."""

    if not isinstance(dimension, int) or isinstance(dimension, bool):
        raise TypeError("dimension muss eine ganze Zahl sein")
    if dimension < 0:
        raise ValueError("dimension darf nicht negativ sein")

    polygons = create_base_surface()
    for _ in range(dimension):
        polygons = perform_inductive_step(polygons)
    return polygons
