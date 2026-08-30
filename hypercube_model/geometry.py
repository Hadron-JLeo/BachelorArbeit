"""Geometrische Operationen der induktiven Konstruktion."""

import numpy as np

from .constants import (
    CUT_FRACTION,
    CUT_MARGIN,
    SHEAR_MARGIN,
    TARGET_HEIGHT,
    ZERO_TOLERANCE,
)
from .models import Polygon3D


def segment_plane_intersection(
    segment_start: np.ndarray,
    segment_end: np.ndarray,
    plane_value_at_start: float,
    plane_value_at_end: float,
) -> np.ndarray:
    """Berechnet den Schnittpunkt einer Strecke mit einer Ebene."""

    start = np.asarray(segment_start, dtype=float)
    end = np.asarray(segment_end, dtype=float)
    if start.shape != (3,) or end.shape != (3,):
        raise ValueError("die Streckenpunkte müssen dreidimensional sein")
    if not np.isfinite(start).all() or not np.isfinite(end).all():
        raise ValueError("die Streckenpunkte müssen endlich sein")

    plane_values = np.array([plane_value_at_start, plane_value_at_end], dtype=float)
    if not np.isfinite(plane_values).all():
        raise ValueError("die Ebenenwerte müssen endlich sein")
    if plane_value_at_start == 0.0 and plane_value_at_end == 0.0:
        raise ValueError("die gesamte Strecke liegt in der Schnittebene")
    if plane_value_at_start == 0.0:
        return start.copy()
    if plane_value_at_end == 0.0:
        return end.copy()
    if np.signbit(plane_value_at_start) == np.signbit(plane_value_at_end):
        raise ValueError("die Schnittebene schneidet die Strecke nicht")

    # Die skalierte Form vermeidet Überläufe bei sehr großen Ebenenwerten.
    absolute_values = np.abs(plane_values)
    scaled_values = absolute_values / absolute_values.max()
    factor = scaled_values[0] / scaled_values.sum()
    intersection = (1.0 - factor) * start + factor * end
    if not np.isfinite(intersection).all():
        raise ValueError("der berechnete Schnittpunkt ist nicht endlich")
    return intersection


def _split_target_vertices(
    polygons: list[Polygon3D],
) -> tuple[np.ndarray, np.ndarray]:
    target = np.concatenate([polygon.vertices[-2:] for polygon in polygons])
    other = np.concatenate([polygon.vertices[:-2] for polygon in polygons])
    return target, other


def _polygon_number(label: str) -> int:
    if not label.startswith("poly_") or not label[5:].isdigit():
        raise ValueError(f"ungültiges Polygonlabel: {label}")
    return int(label[5:])


def shear_and_shift_surface(polygons: list[Polygon3D]) -> None:
    """Bringt die letzte Seite jedes Polygons unter die xy-Ebene."""

    target, other = _split_target_vertices(polygons)
    target_x = target[0, 0]
    if not np.allclose(target[:, 0], target_x, atol=ZERO_TOLERANCE, rtol=0.0):
        raise ValueError("die Zielpunkte liegen nicht auf einer gemeinsamen x-Ebene")

    x_difference = target_x - other[:, 0]
    if np.any(x_difference <= ZERO_TOLERANCE):
        raise ValueError("die Oberfläche erfüllt die Scherungsinvariante nicht")

    # Wegen des gemeinsamen x-Werts genügt das größte z der Zielpunkte.
    # So entstehen keine quadratischen Matrizen über alle Eckpunktpaare.
    z_difference = target[:, 2].max() - other[:, 2]
    shear_strength = np.max(z_difference / x_difference) + SHEAR_MARGIN

    for polygon in polygons:
        polygon.vertices[:, 2] -= shear_strength * polygon.vertices[:, 0]

    target, other = _split_target_vertices(polygons)
    z_shift = -0.5 * (target[:, 2].max() + other[:, 2].min())
    for polygon in polygons:
        polygon.vertices[:, 2] += z_shift

    target, other = _split_target_vertices(polygons)
    if target[:, 2].max() >= 0.0 or other[:, 2].min() <= 0.0:
        raise RuntimeError("Scherung und Verschiebung trennen die Eckpunkte nicht")


def clip_with_xy_plane(polygons: list[Polygon3D]) -> None:
    """Entfernt den Teil jedes Polygons unterhalb der xy-Ebene."""

    for polygon in polygons:
        vertices = polygon.vertices
        upper = segment_plane_intersection(
            vertices[-3], vertices[-2], vertices[-3, 2], vertices[-2, 2]
        )
        lower = segment_plane_intersection(
            vertices[-1], vertices[0], vertices[-1, 2], vertices[0, 2]
        )
        upper[2] = 0.0
        lower[2] = 0.0
        polygon.vertices = np.vstack((vertices[:-2], upper, lower))


def reflect_surface(polygons: list[Polygon3D]) -> list[Polygon3D]:
    """Spiegelt die Oberfläche an der xy-Ebene und verdoppelt sie."""

    reflected = []
    polygon_count = len(polygons)
    polygon_numbers = [_polygon_number(polygon.label) for polygon in polygons]
    if set(polygon_numbers) != set(range(1, polygon_count + 1)):
        raise ValueError("die Polygonlabels müssen eindeutig und fortlaufend sein")

    for polygon in polygons:
        polygon_number = _polygon_number(polygon.label)

        vertices = polygon.vertices.copy()
        vertices[:, 2] *= -1.0
        reflected.append(
            Polygon3D(vertices, label=f"poly_{polygon_number + polygon_count}")
        )

    result = polygons + reflected
    return sorted(result, key=lambda polygon: _polygon_number(polygon.label))


def choose_vertical_cut(polygons: list[Polygon3D]) -> tuple[float, float]:
    """Bestimmt die Parameter der Schnittebene x = a*y + b."""

    vertices = np.stack([polygon.vertices for polygon in polygons])
    b = CUT_FRACTION * vertices[:, -1, 0].min()
    remaining = vertices[:, :-1]
    valid = remaining[:, :, 1] > ZERO_TOLERANCE
    if not np.any(valid):
        raise ValueError("es gibt keine geeigneten Eckpunkte für den Schnitt")

    slopes = (remaining[:, :, 0][valid] - b) / remaining[:, :, 1][valid]
    a = float(slopes.max() + CUT_MARGIN)

    plane_values = vertices[:, :, 0] - a * vertices[:, :, 1] - b
    if np.any(plane_values[:, -1] <= ZERO_TOLERANCE):
        raise RuntimeError("die Schnittebene trennt die letzte Ecke nicht ab")
    if np.any(plane_values[:, :-1] >= -ZERO_TOLERANCE):
        raise RuntimeError("die Schnittebene trennt weitere Ecken ab")

    return a, float(b)


def cut_last_corner(polygons: list[Polygon3D], a: float, b: float) -> None:
    """Schneidet die letzte Ecke jedes Polygons mit derselben Ebene ab."""

    for polygon in polygons:
        vertices = polygon.vertices
        plane_values = vertices[:, 0] - a * vertices[:, 1] - b
        upper = segment_plane_intersection(
            vertices[-2], vertices[-1], plane_values[-2], plane_values[-1]
        )
        lower = segment_plane_intersection(
            vertices[-1], vertices[0], plane_values[-1], plane_values[0]
        )
        polygon.vertices = np.vstack((vertices[:-1], upper, lower))


def apply_projective_transform(
    polygons: list[Polygon3D], a: float, b: float
) -> None:
    """Stellt die Projektionsinvariante für den nächsten Schritt her."""

    if not np.isfinite([a, b]).all():
        raise ValueError("a und b müssen endlich sein")

    for polygon in polygons:
        vertices = polygon.vertices
        denominator = a * vertices[:, 1] + b
        if not np.isfinite(denominator).all():
            raise ValueError("der Nenner der projektiven Transformation ist nicht endlich")
        if np.any(denominator <= ZERO_TOLERANCE):
            raise ValueError("die projektive Transformation überschreitet die Fernebene")

        polygon.vertices = np.column_stack(
            (
                vertices[:, 0] / denominator,
                vertices[:, 1] * (a + b) / denominator,
                vertices[:, 2] / denominator,
            )
        )


def normalize_height(polygons: list[Polygon3D]) -> None:
    """Skaliert die größte absolute z-Koordinate auf TARGET_HEIGHT."""

    maximum_height = max(
        np.abs(polygon.vertices[:, 2]).max() for polygon in polygons
    )
    if not np.isfinite(maximum_height):
        raise ValueError("die Oberfläche enthält nicht endliche Höhenwerte")
    if maximum_height <= ZERO_TOLERANCE:
        raise RuntimeError("die konstruierte Oberfläche besitzt keine Höhe")

    scale_factor = TARGET_HEIGHT / maximum_height
    for polygon in polygons:
        polygon.vertices[:, 2] *= scale_factor
