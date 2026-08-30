"""Validierung der geometrischen und kombinatorischen Konstruktion."""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .models import Polygon3D


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Enthält die überprüften Kenngrößen einer Oberfläche."""

    dimension: int
    polygon_count: int
    vertices_per_polygon: int
    contact_count: int
    boundary_side_count: int


def _validate_polygon(polygon: Polygon3D, tolerance: float) -> None:
    vertices = polygon.vertices
    if not np.isfinite(vertices).all():
        raise ValueError(f"{polygon.label} enthält nicht endliche Koordinaten")

    distances = np.linalg.norm(vertices[:, None, :] - vertices[None, :, :], axis=2)
    distances += np.eye(len(vertices))
    if np.any(distances <= tolerance):
        raise ValueError(f"{polygon.label} enthält wiederholte Eckpunkte")

    edges = np.roll(vertices, -1, axis=0) - vertices
    edge_lengths = np.linalg.norm(edges, axis=1)
    if np.any(edge_lengths <= tolerance):
        raise ValueError(f"{polygon.label} enthält eine entartete Seite")

    centered = vertices - vertices.mean(axis=0)
    _, singular_values, directions = np.linalg.svd(centered, full_matrices=False)
    if singular_values[1] <= tolerance:
        raise ValueError(f"{polygon.label} ist entartet")

    normal = directions[-1]
    plane_distances = np.abs(centered @ normal)
    if plane_distances.max() > tolerance:
        raise ValueError(f"{polygon.label} ist nicht planar")

    projected = centered @ directions[:2].T
    projected_next = np.roll(projected, -1, axis=0)
    signed_area = 0.5 * np.sum(
        projected[:, 0] * projected_next[:, 1]
        - projected[:, 1] * projected_next[:, 0]
    )
    if abs(signed_area) <= tolerance:
        raise ValueError(f"{polygon.label} besitzt keine Fläche")

    projected_edges = projected_next - projected
    next_edges = np.roll(projected_edges, -1, axis=0)
    turns = (
        projected_edges[:, 0] * next_edges[:, 1]
        - projected_edges[:, 1] * next_edges[:, 0]
    )
    turn_scale = np.linalg.norm(projected_edges, axis=1) * np.linalg.norm(
        next_edges, axis=1
    )
    normalized_turns = np.sign(signed_area) * turns / turn_scale
    if np.any(normalized_turns <= tolerance):
        raise ValueError(f"{polygon.label} besitzt kollineare aufeinanderfolgende Seiten")

    # Bei einem konvexen, zyklisch geordneten Polygon liegen alle Eckpunkte
    # in derselben Halbebene jeder gerichteten Polygonseite.
    orientation = np.sign(signed_area)
    for point, edge, edge_length in zip(projected, projected_edges, edge_lengths):
        relative = projected - point
        side_values = orientation * (
            edge[0] * relative[:, 1] - edge[1] * relative[:, 0]
        ) / edge_length
        if side_values.min() < -tolerance:
            raise ValueError(f"{polygon.label} ist nicht konvex oder selbstschneidend")


def _validate_projection_invariant(
    polygon: Polygon3D,
    dimension: int,
    tolerance: float,
) -> None:
    projected = polygon.vertices[:, :2]
    if np.any(projected < -tolerance) or np.any(projected > 1.0 + tolerance):
        raise ValueError(f"{polygon.label} liegt in der Projektion nicht im Einheitsquadrat")

    projected_edges = np.roll(projected, -1, axis=0) - projected
    edge_lengths = np.linalg.norm(projected_edges, axis=1)
    if np.any(edge_lengths <= tolerance):
        raise ValueError(f"{polygon.label} besitzt eine entartete projizierte Seite")

    next_edges = np.roll(projected_edges, -1, axis=0)
    turns = (
        projected_edges[:, 0] * next_edges[:, 1]
        - projected_edges[:, 1] * next_edges[:, 0]
    )
    normalized_turns = turns / (
        edge_lengths * np.roll(edge_lengths, -1)
    )
    if not (
        np.all(normalized_turns > tolerance)
        or np.all(normalized_turns < -tolerance)
    ):
        raise ValueError(f"{polygon.label} besitzt keine strikt konvexe Projektion")

    if not np.allclose(projected[0], [0.0, 0.0], atol=tolerance, rtol=0.0):
        raise ValueError(f"{polygon.label} verletzt die Invariante für p_1")
    if not np.allclose(projected[1], [0.0, 1.0], atol=tolerance, rtol=0.0):
        raise ValueError(f"{polygon.label} verletzt die Invariante für p_2")
    if not np.isclose(projected[2, 1], 1.0, atol=tolerance, rtol=0.0):
        raise ValueError(f"{polygon.label} verletzt die Invariante für p_2p_3")
    if not np.isclose(projected[-2, 0], 1.0, atol=tolerance, rtol=0.0):
        raise ValueError(f"{polygon.label} verletzt die Invariante für p_(k-1)p_k")
    if not np.allclose(projected[-1], [1.0, 0.0], atol=tolerance, rtol=0.0):
        raise ValueError(f"{polygon.label} verletzt die Invariante für p_k")

    if projected[:-2, 0].max() >= 1.0 - tolerance:
        raise ValueError(f"{polygon.label} verletzt die Voraussetzung der Scherung")
    if dimension > 0:
        if projected[2, 0] <= tolerance or projected[2, 0] >= 1.0 - tolerance:
            raise ValueError(f"{polygon.label} besitzt keinen gültigen Punkt p_3")
        if projected[-2, 1] <= tolerance or projected[-2, 1] >= 1.0 - tolerance:
            raise ValueError(f"{polygon.label} besitzt keinen gültigen Punkt p_(k-1)")
        inner_chain = projected[3:-2]
        if inner_chain.size and (
            np.any(inner_chain <= tolerance)
            or np.any(inner_chain >= 1.0 - tolerance)
        ):
            raise ValueError(f"{polygon.label} besitzt keine gültige innere Kette")


def _edge_key(
    first: np.ndarray,
    second: np.ndarray,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    endpoints = (tuple(first), tuple(second))
    return tuple(sorted(endpoints))


def validate_hypercube_surface(
    polygons: list[Polygon3D],
    dimension: int,
    tolerance: float = 1e-9,
) -> ValidationResult:
    """Prüft Geometrie, Projektionsinvariante und Nachbarschaftsgraph.

    Die Prüfung ist auf die deterministisch erzeugten Koordinaten ausgelegt.
    Sie ist kein allgemeiner Kollisionstest für beliebige Polygonflächen.
    """

    if not isinstance(dimension, int) or isinstance(dimension, bool):
        raise TypeError("dimension muss eine ganze Zahl sein")
    if dimension < 0:
        raise ValueError("dimension darf nicht negativ sein")
    if not np.isfinite(tolerance) or tolerance <= 0.0 or tolerance >= 1.0:
        raise ValueError("tolerance muss zwischen 0 und 1 liegen")

    expected_polygon_count = 2**dimension
    expected_vertex_count = dimension + 4
    if len(polygons) != expected_polygon_count:
        raise ValueError(
            f"erwartet: {expected_polygon_count} Polygone; erhalten: {len(polygons)}"
        )

    expected_labels = {f"poly_{index}" for index in range(1, len(polygons) + 1)}
    if {polygon.label for polygon in polygons} != expected_labels:
        raise ValueError("die Polygonlabels sind nicht eindeutig und fortlaufend")
    label_indices = {
        f"poly_{index + 1}": index for index in range(expected_polygon_count)
    }

    edge_occurrences: dict[
        tuple[tuple[float, ...], tuple[float, ...]], list[tuple[int, int]]
    ] = defaultdict(list)
    for polygon in polygons:
        polygon_index = label_indices[polygon.label]
        if len(polygon.vertices) != expected_vertex_count:
            raise ValueError(
                f"{polygon.label} besitzt nicht {expected_vertex_count} Eckpunkte"
            )
        _validate_polygon(polygon, tolerance)
        _validate_projection_invariant(polygon, dimension, tolerance)

        vertices = polygon.vertices
        for side_index, (first, second) in enumerate(
            zip(vertices, np.roll(vertices, -1, axis=0))
        ):
            edge_occurrences[_edge_key(first, second)].append(
                (polygon_index, side_index)
            )

    contacts: set[tuple[int, int]] = set()
    boundary_side_count = 0
    free_side_indices = {0, 1, expected_vertex_count - 2, expected_vertex_count - 1}
    for occurrences in edge_occurrences.values():
        if len(occurrences) == 1:
            if occurrences[0][1] not in free_side_indices:
                raise ValueError("eine erwartete Kontaktseite ist frei")
            boundary_side_count += 1
        elif len(occurrences) == 2:
            if any(side_index in free_side_indices for _, side_index in occurrences):
                raise ValueError("eine freie Seite wurde als Kontakt verwendet")
            if occurrences[0][1] != occurrences[1][1]:
                raise ValueError("ein Kontakt verwendet unterschiedliche Seitenpositionen")

            pair = tuple(sorted(polygon_index for polygon_index, _ in occurrences))
            bit = occurrences[0][1] - 2
            if pair[1] != pair[0] ^ (1 << bit):
                raise ValueError("eine Kontaktseite verbindet die falschen Polygone")
            if pair in contacts:
                raise ValueError("zwei Polygone teilen mehr als eine Seite")
            contacts.add(pair)
        else:
            raise ValueError("eine Seite gehört zu mehr als zwei Polygonen")

    expected_contacts = {
        tuple(sorted((index, index ^ (1 << bit))))
        for index in range(expected_polygon_count)
        for bit in range(dimension)
    }
    if contacts != expected_contacts:
        raise ValueError("der Nachbarschaftsgraph ist nicht der erwartete Hyperwürfel")

    expected_boundary_sides = 4 * expected_polygon_count
    if boundary_side_count != expected_boundary_sides:
        raise ValueError(
            f"erwartet: {expected_boundary_sides} freie Seiten; "
            f"erhalten: {boundary_side_count}"
        )

    return ValidationResult(
        dimension=dimension,
        polygon_count=len(polygons),
        vertices_per_polygon=expected_vertex_count,
        contact_count=len(contacts),
        boundary_side_count=boundary_side_count,
    )
