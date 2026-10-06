"""Blender-Szene und .blend-Export der erzeugten Polygonfamilie."""

from __future__ import annotations

import colorsys
import json
from numbers import Integral
from pathlib import Path

import numpy as np

from .model import Polygon3D


def surface_payload(polygons: list[Polygon3D], dimension: int) -> dict:
    """Serialisiert die Generatorreihenfolge samt Hyperwürfel-Nachbarn."""
    if isinstance(dimension, (bool, np.bool_)) or not isinstance(
        dimension, Integral
    ):
        raise TypeError("dimension muss eine ganze Zahl sein.")
    dimension = int(dimension)
    if dimension < 0 or len(polygons) != 2 ** dimension:
        raise ValueError(
            "Die Polygonzahl muss 2**dimension mit dimension >= 0 sein."
        )
    if any(len(polygon.vertices) != dimension + 4 for polygon in polygons):
        raise ValueError("Jedes Polygon muss dimension + 4 Ecken besitzen.")

    records = []
    for index, polygon in enumerate(polygons):
        graph_bits = format(index, f"0{dimension}b") if dimension else ""
        records.append(
            {
                "index": index,
                "label": polygon.label,
                "graph_bits": graph_bits,
                "construction_path": graph_bits[::-1],
                "neighbor_indices": [
                    index ^ (1 << bit) for bit in range(dimension)
                ],
                "vertices": np.asarray(
                    polygon.vertices, dtype=float
                ).tolist(),
            }
        )
    return {
        "schema_version": 2,
        "dimension": dimension,
        "coordinate_system": (
            "NumPy x/y/z unverändert, keine Achsendrehung oder Skalierung"
        ),
        "hierarchy": (
            "chronologischer Induktionspfad; 0=Original, 1=Spiegelbild"
        ),
        "polygons": records,
    }


def build_blender_scene(data: dict) -> dict:
    """Erzeugt die vollständige Blender-Szene im aktiven Python-Prozess."""
    import bpy
    from mathutils import Quaternion, Vector

    if not bpy.app.background:
        raise RuntimeError("Dieses Minimal-bpy ist nur für Headless-Export gedacht.")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    dimension = int(data["dimension"])
    records = data["polygons"]
    scene.name = f"Q{dimension}_Polygonfamilie"

    model_collection = bpy.data.collections.new(f"Q{dimension}_Modell")
    scene.collection.children.link(model_collection)
    points = [
        Vector(vertex)
        for record in records
        for vertex in record["vertices"]
    ]
    lower = Vector(
        tuple(min(point[axis] for point in points) for axis in range(3))
    )
    upper = Vector(
        tuple(max(point[axis] for point in points) for axis in range(3))
    )
    center = (lower + upper) / 2
    extent = max((upper - lower).length, 1.0)

    def empty(name: str, parent=None):
        obj = bpy.data.objects.new(name, None)
        model_collection.objects.link(obj)
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = extent * 0.04
        obj.parent = parent
        return obj

    root = empty(f"Q{dimension}_Gesamtmodell")
    root.location = center
    root["role"] = "model_root"
    root["dimension"] = dimension
    root["polygon_count"] = len(records)
    root["hierarchy"] = (
        "Induktionspfad: links zuerst Schritt 1; "
        "0=Original, 1=Spiegelbild"
    )

    groups = {"": root}
    materials = []
    for index in range(8):
        rgb = colorsys.hsv_to_rgb(index / 8, 0.48, 0.72)
        material = bpy.data.materials.new(f"Polygonfarbe_{index + 1:02d}")
        material.diffuse_color = (*rgb, 1.0)
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*rgb, 1.0)
        shader.inputs["Roughness"].default_value = 0.65
        materials.append(material)

    polygon_objects = []
    for record in records:
        path = record["construction_path"]
        for depth in range(1, len(path)):
            prefix = path[:depth]
            if prefix not in groups:
                group = empty(
                    f"Schritt_{depth:02d}_{prefix}",
                    groups[prefix[:-1]],
                )
                group["role"] = "construction_group"
                group["construction_path"] = prefix
                group["step"] = depth
                groups[prefix] = group

        vertices = record["vertices"]
        origin_xyz = tuple(
            sum(vertex[axis] for vertex in vertices) / len(vertices)
            for axis in range(3)
        )
        origin = Vector(origin_xyz)
        local_vertices = [
            tuple(vertex[axis] - origin_xyz[axis] for axis in range(3))
            for vertex in vertices
        ]
        name = f"Polygon_{path or 'Basis'}"
        mesh = bpy.data.meshes.new(name + "_Mesh")
        mesh.from_pydata(
            local_vertices,
            [],
            [list(range(len(vertices)))],
        )
        mesh.update()

        obj = bpy.data.objects.new(name, mesh)
        model_collection.objects.link(obj)
        obj.parent = groups.get(path[:-1], root)
        obj.location = origin - center
        obj["role"] = "source_polygon"
        obj["source_index"] = record["index"]
        obj["source_label"] = record["label"]
        obj["construction_path"] = path
        obj["graph_bits"] = record["graph_bits"]
        obj["vertex_count_numpy"] = len(vertices)
        obj["neighbor_indices_json"] = json.dumps(
            record["neighbor_indices"]
        )
        color_index = int((path[:3] or "0").ljust(3, "0"), 2)
        obj.data.materials.append(materials[color_index])
        obj.color = materials[color_index].diffuse_color
        obj.show_wire = True
        obj.show_all_edges = True
        polygon_objects.append(obj)

    bpy.context.view_layer.update()
    source_text = bpy.data.texts.new("NumPy_Quelldaten.json")
    source_text.write(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    )
    readme = bpy.data.texts.new("LIESMICH_Blender")
    readme.write(
        "Gesamtmodell: Q*_Gesamtmodell auswählen und G/R/S verwenden.\n"
        "Schritt-Gruppen bewegen ihre Polygon-Nachkommen.\n"
        "Einzelne Polygone sind eigenständige Mesh-Objekte.\n"
        "Tab wechselt für ein Polygon in den Bearbeitungsmodus.\n"
        "0=Original und 1=Spiegelbild im chronologischen Induktionspfad.\n"
        "Die Hierarchie ist kein Adjazenzbaum.\n"
        "Nachbarn stehen in neighbor_indices_json.\n"
        "Die Text-Quelldaten enthalten die float64-Koordinaten.\n"
        "Punkte wurden nicht verschmolzen; die Familie hat freie Ränder.\n"
        "Für den Blick ins Innere: X-Ray oder Drahtgitter verwenden.\n"
    )

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "SOLID"
                space.shading.color_type = "MATERIAL"
                space.shading.show_cavity = True
                space.region_3d.view_location = center
                space.region_3d.view_distance = extent * 1.65
                space.region_3d.view_rotation = Quaternion(
                    (0.820, 0.425, 0.176, 0.340)
                ).normalized()
                space.clip_start = 0.0001
                space.clip_end = extent * 100

    bpy.context.view_layer.objects.active = root
    root.select_set(True)
    return {
        "blender_version": bpy.app.version_string,
        "dimension": dimension,
        "mesh_objects": len(polygon_objects),
        "mesh_faces": sum(
            len(obj.data.polygons) for obj in polygon_objects
        ),
        "mesh_vertices": sum(
            len(obj.data.vertices) for obj in polygon_objects
        ),
        "empty_objects": len(groups),
    }


def export_surface_to_blend(
    polygons: list[Polygon3D],
    dimension: int,
    filepath: str | Path,
    *,
    overwrite: bool = False,
) -> dict:
    """Speichert Oberfläche, Metadaten und Hierarchie direkt als .blend."""
    import bpy

    path = Path(filepath).expanduser().resolve()
    if path.suffix.lower() != ".blend":
        raise ValueError("Der Zielpfad muss auf .blend enden.")
    if path.exists() and not overwrite:
        raise FileExistsError(path)

    data = surface_payload(polygons, dimension)
    path.parent.mkdir(parents=True, exist_ok=True)
    json_path = path.with_suffix(".json")
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    result = build_blender_scene(data)
    bpy.context.preferences.filepaths.save_version = 0
    save_result = bpy.ops.wm.save_as_mainfile(
        filepath=str(path),
        check_existing=False,
        compress=True,
    )
    if save_result != {"FINISHED"} or not path.is_file():
        raise RuntimeError(f"Die .blend-Datei wurde nicht geschrieben: {path}")
    return {
        **result,
        "blend_path": str(path),
        "json_path": str(json_path),
        "blend_bytes": path.stat().st_size,
    }
