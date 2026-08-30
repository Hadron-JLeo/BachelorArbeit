"""Konvertierung nach Open3D und interaktive Plotly-Darstellung."""

import numpy as np
import open3d as o3d
import plotly.graph_objects as go
from open3d.visualization.draw_plotly import get_plotly_fig

from .constants import (
    EDGE_COLOR,
    MODEL_COLOR,
    MODEL_OPACITY,
    VIEW_HEIGHT,
    VIEW_WIDTH,
)
from .models import Polygon3D


def create_open3d_model(
    polygons: list[Polygon3D],
) -> tuple[o3d.geometry.TriangleMesh, o3d.geometry.LineSet]:
    """Erzeugt ein Open3D-Modell für die Visualisierung.

    Die Polygonpunkte bleiben im Dreiecksnetz absichtlich getrennt. Der
    Nachbarschaftsgraph wird aus den Polygonseiten und nicht aus dem Mesh gelesen.
    """

    if not polygons:
        raise ValueError("mindestens ein Polygon wird benötigt")

    vertex_blocks = []
    triangle_blocks = []
    line_blocks = []
    offset = 0

    for polygon in polygons:
        count = len(polygon.vertices)
        indices = np.arange(offset, offset + count)
        triangle_blocks.append(
            np.column_stack(
                (np.full(count - 2, offset), indices[1:-1], indices[2:])
            )
        )
        line_blocks.append(np.column_stack((indices, np.roll(indices, -1))))
        vertex_blocks.append(polygon.vertices)
        offset += count

    vertices = np.vstack(vertex_blocks)
    triangles = np.vstack(triangle_blocks)
    lines = np.vstack(line_blocks)

    mesh = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(vertices),
        o3d.utility.Vector3iVector(triangles),
    )
    edges = o3d.geometry.LineSet(
        o3d.utility.Vector3dVector(vertices),
        o3d.utility.Vector2iVector(lines),
    )
    return mesh, edges


def show_open3d_model(
    mesh: o3d.geometry.TriangleMesh,
    edges: o3d.geometry.LineSet,
) -> go.Figure:
    """Zeigt das Open3D-Modell als interaktive Plotly-Grafik."""

    figure = get_plotly_fig([mesh, edges], width=VIEW_WIDTH, height=VIEW_HEIGHT)
    for trace in figure.data:
        if trace.type == "mesh3d":
            trace.update(
                color=MODEL_COLOR,
                opacity=MODEL_OPACITY,
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
            trace.update(line={"color": EDGE_COLOR, "width": 2})

    figure.update_layout(
        title="Oberfläche des Hyperwürfelgraphen",
        scene={
            "aspectmode": "data",
            "xaxis": {"title": "x", "showticklabels": False},
            "yaxis": {"title": "y", "showticklabels": False},
            "zaxis": {"title": "z", "showticklabels": False},
        },
    )
    figure.show()
    return figure
