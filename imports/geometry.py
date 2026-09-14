"""Elementary transformations used by the inductive construction."""

from __future__ import annotations

import numpy as np

from .config import DEFAULT_GEOMETRY_CONFIG
from .model import Polygon3D


def segment_plane_intersection(
    segment_start: np.ndarray,
    segment_end: np.ndarray,
    plane_value_at_start: float,
    plane_value_at_end: float,
    *,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> np.ndarray:
    """Calculate a unique plane intersection lying within a line segment."""
    f_start, f_end = plane_value_at_start, plane_value_at_end
    denominator = f_start - f_end
    scale = max(abs(f_start), abs(f_end))
    if (
        not np.isfinite([f_start, f_end, denominator]).all()
        or scale == 0
        or abs(denominator) <= tolerance * scale
    ):
        raise ValueError("Die Strecke besitzt keinen numerisch eindeutigen Ebenenschnitt.")
    factor = f_start / denominator
    if not 0 <= factor <= 1:
        raise ValueError("Der Ebenenschnitt liegt außerhalb der Strecke.")
    return segment_start + factor * (segment_end - segment_start)


def get_target_and_other_points(
    polygons: list[Polygon3D],
) -> tuple[np.ndarray, np.ndarray]:
    """Separate the last two vertices of every polygon from all other vertices."""
    if not polygons:
        raise ValueError("Die Oberfläche darf nicht leer sein.")
    target = np.concatenate([polygon.vertices[-2:] for polygon in polygons])
    other = np.concatenate([polygon.vertices[:-2] for polygon in polygons])
    return target, other


def apply_z_shear(
    polygons: list[Polygon3D],
    *,
    margin: float = DEFAULT_GEOMETRY_CONFIG.shear_margin,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Shear z while leaving x and y unchanged."""
    if not np.isfinite(margin) or margin <= 0:
        raise ValueError("Der Scherungsabstand muss positiv und endlich sein.")
    target, other = get_target_and_other_points(polygons)
    x_distances = target[:, 0].min() - other[:, 0]
    if np.any(x_distances <= tolerance):
        raise ValueError("Die Zielpunkte müssen rechts von allen übrigen Punkten liegen.")
    slopes = (target[:, 2].max() - other[:, 2]) / x_distances
    shear_strength = max(0.0, float(slopes.max())) + margin
    for polygon in polygons:
        polygon.vertices[:, 2] -= shear_strength * polygon.vertices[:, 0]


def apply_z_shift(
    polygons: list[Polygon3D],
    *,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Center the height gap between target and other vertices on z=0."""
    target, other = get_target_and_other_points(polygons)
    target_top, other_bottom = target[:, 2].max(), other[:, 2].min()
    if other_bottom - target_top <= tolerance:
        raise ValueError("Die Scherung hat keine ausreichend große Höhenlücke erzeugt.")
    z_shift = -0.5 * (target_top + other_bottom)
    for polygon in polygons:
        polygon.vertices[:, 2] += z_shift


def clip_with_xy_plane(
    polygons: list[Polygon3D],
    *,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Keep the part above z=0 for the construction's vertex ordering."""
    for polygon in polygons:
        vertices = polygon.vertices
        if not (
            np.all(vertices[-2:, 2] < -tolerance)
            and np.all(vertices[:-2, 2] > tolerance)
        ):
            raise ValueError("Der Horizontalschnitt würde unerwartete Ecken entfernen.")
        upper = segment_plane_intersection(
            vertices[-3],
            vertices[-2],
            vertices[-3, 2],
            vertices[-2, 2],
            tolerance=tolerance,
        )
        lower = segment_plane_intersection(
            vertices[-1],
            vertices[0],
            vertices[-1, 2],
            vertices[0, 2],
            tolerance=tolerance,
        )
        upper[2] = lower[2] = 0.0
        polygon.vertices = np.vstack((vertices[:-2], upper, lower))


def reflect_surface(polygons: list[Polygon3D]) -> list[Polygon3D]:
    """Append independent reflections across the xy plane."""
    reflected = [
        Polygon3D(polygon.vertices * np.array([1.0, 1.0, -1.0]))
        for polygon in polygons
    ]
    return polygons + reflected


# Die Parameterwahl wurde im Original als mit generativer KI erstellt gekennzeichnet.
def choose_vertical_cut(
    polygons: list[Polygon3D],
    *,
    fraction: float = DEFAULT_GEOMETRY_CONFIG.cut_fraction,
    margin: float = DEFAULT_GEOMETRY_CONFIG.cut_margin,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> tuple[float, float]:
    """Choose x=a*y+b and verify the signs at every vertex."""
    if not 0 < fraction < 1:
        raise ValueError("fraction muss zwischen 0 und 1 liegen.")
    if not np.isfinite(margin) or margin <= 0:
        raise ValueError("margin muss positiv und endlich sein.")
    if not polygons:
        raise ValueError("Die Oberfläche darf nicht leer sein.")
    b = fraction * min(polygon.vertices[-1, 0] for polygon in polygons)
    remaining = np.concatenate([polygon.vertices[:-1] for polygon in polygons])
    positive_y = remaining[:, 1] > tolerance
    if not positive_y.any() or b <= tolerance:
        raise ValueError("Für diese Oberfläche lässt sich der vorgesehene Schnitt nicht wählen.")
    slopes = (remaining[positive_y, 0] - b) / remaining[positive_y, 1]
    a = float(slopes.max()) + margin
    for polygon in polygons:
        values = polygon.vertices[:, 0] - a * polygon.vertices[:, 1] - b
        if not (
            np.all(values[:-1] < -tolerance) and values[-1] > tolerance
        ):
            raise ValueError("Die vertikale Ebene trennt nicht genau die letzte Ecke ab.")
    return a, float(b)


def cut_last_corner(
    polygons: list[Polygon3D],
    a: float,
    b: float,
    *,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Replace the last vertex of each polygon by two plane intersections."""
    for polygon in polygons:
        vertices = polygon.vertices
        values = vertices[:, 0] - a * vertices[:, 1] - b
        if not (
            np.all(values[:-1] < -tolerance) and values[-1] > tolerance
        ):
            raise ValueError("Ungültige Vorzeichen für den Eckenschnitt.")
        upper = segment_plane_intersection(
            vertices[-2],
            vertices[-1],
            values[-2],
            values[-1],
            tolerance=tolerance,
        )
        lower = segment_plane_intersection(
            vertices[-1],
            vertices[0],
            values[-1],
            values[0],
            tolerance=tolerance,
        )
        polygon.vertices = np.vstack((vertices[:-1], upper, lower))


def apply_projective_transform(
    polygons: list[Polygon3D],
    a: float,
    b: float,
    *,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Map the cut side back to x=1 without general coordinate rounding."""
    denominators = [a * polygon.vertices[:, 1] + b for polygon in polygons]
    if any(
        not np.isfinite(values).all() or np.any(values <= tolerance)
        for values in denominators
    ):
        raise ValueError(
            "Die projektive Abbildung besitzt einen nichtpositiven oder zu kleinen Nenner."
        )
    for polygon, denominator in zip(polygons, denominators):
        polygon.vertices = (
            polygon.vertices * np.array([1.0, a + b, 1.0])
            / denominator[:, None]
        )


def normalize_height(
    polygons: list[Polygon3D],
    *,
    target_height: float = DEFAULT_GEOMETRY_CONFIG.target_height,
    tolerance: float = DEFAULT_GEOMETRY_CONFIG.zero_tolerance,
) -> None:
    """Scale the maximum absolute height without building a combined array."""
    if not np.isfinite(target_height) or target_height <= 0:
        raise ValueError("target_height muss positiv und endlich sein.")
    if not polygons:
        raise ValueError("Die Oberfläche darf nicht leer sein.")
    maximum_height = max(
        float(np.abs(polygon.vertices[:, 2]).max()) for polygon in polygons
    )
    if not np.isfinite(maximum_height):
        raise ValueError("Die Oberfläche enthält nichtendliche Höhen.")
    if maximum_height <= tolerance:
        return
    for polygon in polygons:
        polygon.vertices[:, 2] *= target_height / maximum_height


__all__ = [
    "apply_projective_transform",
    "apply_z_shear",
    "apply_z_shift",
    "choose_vertical_cut",
    "clip_with_xy_plane",
    "cut_last_corner",
    "get_target_and_other_points",
    "normalize_height",
    "reflect_surface",
    "segment_plane_intersection",
]
