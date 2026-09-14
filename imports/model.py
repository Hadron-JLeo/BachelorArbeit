"""Data model used by the geometric construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True, eq=False)
class Polygon3D:
    """Stores cyclically ordered polygon vertices and a local label."""

    vertices: np.ndarray
    label: str = ""

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 3:
            raise ValueError(
                "Polygonecken müssen ein Array der Form (n, 3), n >= 3, bilden."
            )
        if not np.isfinite(vertices).all():
            raise ValueError("Polygonecken müssen endliche Koordinaten besitzen.")
        self.vertices = vertices.copy()

