"""Public interface for hypercube surface construction."""

from .config import (
    DEFAULT_GEOMETRY_CONFIG,
    DEFAULT_VISUALIZATION_CONFIG,
    GeometryConfig,
    VisualizationConfig,
)
from .construction import (
    create_base_surface,
    generate_hypercube_surface,
    perform_inductive_step,
)
from .model import Polygon3D

__all__ = [
    "DEFAULT_GEOMETRY_CONFIG",
    "DEFAULT_VISUALIZATION_CONFIG",
    "GeometryConfig",
    "Polygon3D",
    "VisualizationConfig",
    "create_base_surface",
    "generate_hypercube_surface",
    "perform_inductive_step",
]

__version__ = "0.1.0"

