"""Datenstrukturen der polyedrischen Oberfläche."""

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True, eq=False)
class Polygon3D:
    """Speichert die geordneten Eckpunkte eines Polygons."""

    vertices: np.ndarray
    label: str = "polygon"

    def __post_init__(self) -> None:
        vertices = np.array(self.vertices, dtype=float, copy=True)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError("vertices muss die Form (n, 3) haben")
        if len(vertices) < 3:
            raise ValueError("ein Polygon benötigt mindestens drei Eckpunkte")
        if not np.isfinite(vertices).all():
            raise ValueError("vertices darf nur endliche Koordinaten enthalten")
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("label muss eine nichtleere Zeichenkette sein")

        self.vertices = vertices
