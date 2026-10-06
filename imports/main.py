"""Kurzer Einstiegspunkt für Konstruktion, Blender-Export und Download."""

from __future__ import annotations

import os
from pathlib import Path

from .blender_export import export_surface_to_blend
from .config import DEFAULT_GEOMETRY_CONFIG, GeometryConfig
from .construction import generate_hypercube_surface


def _offer_download(path: Path) -> None:
    """Startet den Colab-Download oder zeigt einen lokalen Notebook-Link."""
    try:
        from google.colab import files
    except ImportError:
        try:
            from IPython import get_ipython
            from IPython.display import FileLink, display
        except ImportError:
            return
        if get_ipython() is not None:
            display(FileLink(os.path.relpath(path, Path.cwd())))
    else:
        files.download(str(path))


def main(
    dimension: int = 4,
    *,
    config: GeometryConfig = DEFAULT_GEOMETRY_CONFIG,
    output_directory: str | Path = "blender_export",
    download: bool = True,
    overwrite: bool = True,
) -> Path:
    """Erzeugt Q_dimension und gibt den Pfad seiner Blender-Datei zurück."""
    surface = generate_hypercube_surface(dimension, config=config)
    path = Path(output_directory) / f"Q{dimension}_Hypercube_Polygonfamilie.blend"
    result = export_surface_to_blend(
        surface, dimension, path, overwrite=overwrite
    )
    path = Path(result["blend_path"])
    print(f"Q_{dimension}: {len(surface)} Polygone → {path.name}")
    if download:
        _offer_download(path)
    return path
