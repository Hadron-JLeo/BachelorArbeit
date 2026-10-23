"""Elementary transformations used by the inductive construction.

All polygons of one construction stage have the same vertex count k = d + 4, so
the surface is processed as a single array ``vertices`` of shape (n, k, 3)
instead of polygon by polygon.
"""

from __future__ import annotations

import numpy as np

from .config import GeometryConfig


def segment_plane_intersection(
    start: np.ndarray,
    end: np.ndarray,
    f_start: np.ndarray,
    f_end: np.ndarray,
    tolerance: float,
) -> np.ndarray:
    """Intersect segments start→end with the plane whose signed values are f."""
    denominator = f_start - f_end
    scale = np.maximum(np.abs(f_start), np.abs(f_end))
    if (
        not np.isfinite([f_start, f_end, denominator]).all()
        or np.any(scale == 0)
        or np.any(np.abs(denominator) <= tolerance * scale)
    ):
        raise ValueError("Die Strecke besitzt keinen numerisch eindeutigen Ebenenschnitt.")
    factor = f_start / denominator
    if not np.all((0 <= factor) & (factor <= 1)):
        raise ValueError("Der Ebenenschnitt liegt außerhalb der Strecke.")
    return start + factor[..., None] * (end - start)


def apply_z_shear(vertices: np.ndarray, config: GeometryConfig) -> None:
    """Shear z in place while leaving x and y unchanged."""
    x_distances = vertices[:, -2:, 0].min() - vertices[:, :-2, 0]
    if np.any(x_distances <= config.zero_tolerance):
        raise ValueError("Die Zielpunkte müssen rechts von allen übrigen Punkten liegen.")
    slopes = (vertices[:, -2:, 2].max() - vertices[:, :-2, 2]) / x_distances
    shear_strength = max(0.0, float(slopes.max())) + config.shear_margin
    vertices[..., 2] -= shear_strength * vertices[..., 0]


def apply_z_shift(vertices: np.ndarray, config: GeometryConfig) -> None:
    """Center the height gap between target and other vertices on z=0 (in place)."""
    target_top, other_bottom = vertices[:, -2:, 2].max(), vertices[:, :-2, 2].min()
    if other_bottom - target_top <= config.zero_tolerance:
        raise ValueError("Die Scherung hat keine ausreichend große Höhenlücke erzeugt.")
    vertices[..., 2] += -0.5 * (target_top + other_bottom)


def clip_with_xy_plane(vertices: np.ndarray, config: GeometryConfig) -> np.ndarray:
    """Keep the part above z=0 for the construction's vertex ordering."""
    tolerance, z = config.zero_tolerance, vertices[..., 2]
    if not (np.all(z[:, -2:] < -tolerance) and np.all(z[:, :-2] > tolerance)):
        raise ValueError("Der Horizontalschnitt würde unerwartete Ecken entfernen.")
    start, end = [-3, -1], [-2, 0]
    cut = segment_plane_intersection(
        vertices[:, start], vertices[:, end], z[:, start], z[:, end], tolerance
    )
    cut[..., 2] = 0.0
    return np.concatenate((vertices[:, :-2], cut), axis=1)


def reflect_surface(vertices: np.ndarray) -> np.ndarray:
    """Append reflections across the xy plane after the originals."""
    return np.concatenate((vertices, vertices * np.array([1.0, 1.0, -1.0])))


# Die Parameterwahl wurde im Original als mit generativer KI erstellt gekennzeichnet.
def cut_last_corner(
    vertices: np.ndarray, config: GeometryConfig
) -> tuple[np.ndarray, float, float]:
    """Choose x=a*y+b, verify the signs and replace each last vertex by two cuts."""
    tolerance = config.zero_tolerance
    b = config.cut_fraction * vertices[:, -1, 0].min()
    x, y = vertices[:, :-1, 0], vertices[:, :-1, 1]
    positive_y = y > tolerance
    if not positive_y.any() or b <= tolerance:
        raise ValueError("Für diese Oberfläche lässt sich der vorgesehene Schnitt nicht wählen.")
    slopes = (x[positive_y] - b) / y[positive_y]
    a = float(slopes.max()) + config.cut_margin
    values = vertices[..., 0] - a * vertices[..., 1] - b
    if not (np.all(values[:, :-1] < -tolerance) and np.all(values[:, -1] > tolerance)):
        raise ValueError("Die vertikale Ebene trennt nicht genau die letzte Ecke ab.")
    start, end = [-2, -1], [-1, 0]
    cut = segment_plane_intersection(
        vertices[:, start], vertices[:, end], values[:, start], values[:, end], tolerance
    )
    return np.concatenate((vertices[:, :-1], cut), axis=1), a, float(b)


def apply_projective_transform(
    vertices: np.ndarray, a: float, b: float, config: GeometryConfig
) -> np.ndarray:
    """Map the cut side back to x=1 without general coordinate rounding."""
    denominator = a * vertices[..., 1] + b
    if not np.isfinite(denominator).all() or np.any(denominator <= config.zero_tolerance):
        raise ValueError(
            "Die projektive Abbildung besitzt einen nichtpositiven oder zu kleinen Nenner."
        )
    return vertices * np.array([1.0, a + b, 1.0]) / denominator[..., None]


def normalize_height(vertices: np.ndarray, config: GeometryConfig) -> None:
    """Scale the maximum absolute height to config.target_height (in place)."""
    maximum_height = float(np.abs(vertices[..., 2]).max())
    if not np.isfinite(maximum_height):
        raise ValueError("Die Oberfläche enthält nichtendliche Höhen.")
    if maximum_height > config.zero_tolerance:
        vertices[..., 2] *= config.target_height / maximum_height


__all__ = [
    "apply_projective_transform",
    "apply_z_shear",
    "apply_z_shift",
    "clip_with_xy_plane",
    "cut_last_corner",
    "normalize_height",
    "reflect_surface",
    "segment_plane_intersection",
]
