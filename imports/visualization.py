"""Open3D/Plotly visualization and readable coordinate output."""

from __future__ import annotations

from numbers import Integral
from typing import TYPE_CHECKING

import numpy as np

from .config import DEFAULT_VISUALIZATION_CONFIG, VisualizationConfig
from .model import Polygon3D

if TYPE_CHECKING:
    import open3d as o3d
    from plotly.graph_objects import Figure


# Im Ausgangsnotebook als KI-unterstützte Visualisierung gekennzeichnet.
def create_open3d_model(
    polygons: list[Polygon3D],
    *,
    config: VisualizationConfig = DEFAULT_VISUALIZATION_CONFIG,
) -> tuple[o3d.geometry.TriangleMesh, o3d.geometry.LineSet]:
    """Create a display mesh and the original polygon edges."""
    import open3d as o3d

    if not polygons:
        raise ValueError("Die Oberfläche darf nicht leer sein.")

    mesh_vertices = []
    mesh_triangles = []
    edge_lines = []
    vertex_offset = 0

    for polygon in polygons:
        vertex_count = len(polygon.vertices)
        vertex_indices = np.arange(vertex_offset, vertex_offset + vertex_count)
        triangles = np.column_stack(
            (
                np.full(vertex_count - 2, vertex_offset),
                vertex_indices[1:-1],
                vertex_indices[2:],
            )
        )
        lines = np.column_stack((vertex_indices, np.roll(vertex_indices, -1)))

        mesh_vertices.append(polygon.vertices)
        mesh_triangles.append(triangles)
        edge_lines.append(lines)
        vertex_offset += vertex_count

    vertices = np.vstack(mesh_vertices)
    triangles = np.vstack(mesh_triangles)
    lines = np.vstack(edge_lines)

    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(vertices)
    mesh.triangles = o3d.utility.Vector3iVector(triangles)
    mesh.compute_vertex_normals()

    edges = o3d.geometry.LineSet()
    edges.points = o3d.utility.Vector3dVector(vertices)
    edges.lines = o3d.utility.Vector2iVector(lines)
    edge_color = np.asarray(config.edge_color, dtype=float)
    edges.colors = o3d.utility.Vector3dVector(np.tile(edge_color, (len(lines), 1)))
    return mesh, edges


# Grundlage laut Ausgangsnotebook generativ erstellt und anschließend dokumentiert.
def show_open3d_model(
    mesh: o3d.geometry.TriangleMesh,
    edges: o3d.geometry.LineSet,
    *,
    renderer: str | None = None,
    title: str = "Polygonfamilie für einen Hyperwürfelgraphen",
    config: VisualizationConfig = DEFAULT_VISUALIZATION_CONFIG,
) -> Figure:
    """Show a model with Plotly and return its figure."""
    from open3d.visualization.draw_plotly import get_plotly_fig

    figure = get_plotly_fig([mesh, edges], width=config.width, height=config.height)
    edge_color = np.asarray(config.edge_color, dtype=float)

    for trace in figure.data:
        if trace.type == "mesh3d":
            trace.update(
                color=config.model_color,
                opacity=config.opacity,
                intensity=None,
                colorscale=None,
                showscale=False,
                flatshading=True,
                lighting={
                    "ambient": 0.8,
                    "diffuse": 0.5,
                    "specular": 0.0,
                    "roughness": 1.0,
                    "fresnel": 0.0,
                },
            )
        elif trace.type == "scatter3d":
            trace.update(
                line={
                    "color": "rgb({},{},{})".format(
                        *(int(round(255 * value)) for value in edge_color)
                    ),
                    "width": 2,
                }
            )

    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 0, "r": 0, "t": 55, "b": 0},
        scene={
            "camera": {"eye": {"x": 1.6, "y": -2.0, "z": 1.2}},
            "aspectmode": "data",
            "xaxis": {"title": "x", "showticklabels": False},
            "yaxis": {"title": "y", "showticklabels": False},
            "zaxis": {"title": "z", "showticklabels": False},
        },
    )
    figure.show(renderer=renderer)
    return figure


def print_vertex_coordinates(
    polygons: list[Polygon3D],
    *,
    precision: int = 17,
) -> None:
    """Print every polygon vertex with labels and NumPy coordinates."""
    if isinstance(precision, (bool, np.bool_)) or not isinstance(precision, Integral):
        raise TypeError("precision muss eine ganze Zahl sein.")
    if not 1 <= precision <= 17:
        raise ValueError("precision muss zwischen 1 und 17 liegen.")

    rows = []
    for polygon_index, polygon in enumerate(polygons, start=1):
        polygon_label = polygon.label or f"poly_{polygon_index}"
        for vertex_index, vertex in enumerate(polygon.vertices, start=1):
            vertex_label = f"P{polygon_index:03d}_E{vertex_index:03d}"
            coordinates = [format(float(value), f".{precision}g") for value in vertex]
            rows.append([polygon_label, vertex_label, *coordinates])

    headings = ["Polygon", "Eckpunkt", "x", "y", "z"]
    widths = (
        [
            max(len(heading), *(len(row[column]) for row in rows))
            for column, heading in enumerate(headings)
        ]
        if rows
        else list(map(len, headings))
    )
    print(" | ".join(heading.ljust(width) for heading, width in zip(headings, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(
            " | ".join(
                value.ljust(width) if column < 2 else value.rjust(width)
                for column, (value, width) in enumerate(zip(row, widths))
            )
        )
    print(f"\nEckpunkte insgesamt (pro Polygon gezählt): {len(rows)}")


__all__ = [
    "create_open3d_model",
    "print_vertex_coordinates",
    "show_open3d_model",
]
