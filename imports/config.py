"""Configurable numerical and visual defaults."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    """Numerical parameters of one inductive construction step."""

    shear_margin: float = 1.0
    # Die Parameterwahl wurde im Original als KI-unterstützt gekennzeichnet.
    cut_fraction: float = 0.92
    cut_margin: float = 0.05
    zero_tolerance: float = 1e-12
    target_height: float = 1.0

    def __post_init__(self) -> None:
        positive_values = {
            "shear_margin": self.shear_margin,
            "cut_margin": self.cut_margin,
            "zero_tolerance": self.zero_tolerance,
            "target_height": self.target_height,
        }
        for name, value in positive_values.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} muss positiv und endlich sein.")
        if not math.isfinite(self.cut_fraction) or not 0 < self.cut_fraction < 1:
            raise ValueError("cut_fraction muss zwischen 0 und 1 liegen.")


@dataclass(frozen=True, slots=True)
class VisualizationConfig:
    """Appearance and output size of the Open3D/Plotly view."""

    model_color: str = "rgb(45, 105, 210)"
    edge_color: tuple[float, float, float] = (0.08, 0.08, 0.08)
    width: int = 1000
    height: int = 700
    opacity: float = 0.30

    def __post_init__(self) -> None:
        if len(self.edge_color) != 3 or any(
            not math.isfinite(value) or not 0 <= value <= 1
            for value in self.edge_color
        ):
            raise ValueError("edge_color muss aus drei Werten zwischen 0 und 1 bestehen.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width und height müssen positiv sein.")
        if not math.isfinite(self.opacity) or not 0 <= self.opacity <= 1:
            raise ValueError("opacity muss zwischen 0 und 1 liegen.")


DEFAULT_GEOMETRY_CONFIG = GeometryConfig()
DEFAULT_VISUALIZATION_CONFIG = VisualizationConfig()
