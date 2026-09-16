"""Writer-/Reader-Pflichttest für das minimale bpy-Wheel."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector


def snapshot() -> dict:
    bpy.context.view_layer.update()
    objects = {}
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        state = {
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "collections": sorted(collection.name for collection in obj.users_collection),
            "matrix": [list(row) for row in obj.matrix_world],
            "color": list(obj.color),
            "properties": {key: obj[key] for key in sorted(obj.keys())},
        }
        if obj.type == "EMPTY":
            state["empty"] = [obj.empty_display_type, obj.empty_display_size]
        elif obj.type == "MESH":
            state.update({
                "vertices": [list(vertex.co) for vertex in obj.data.vertices],
                "edges": [list(edge.vertices) for edge in obj.data.edges],
                "faces": [list(face.vertices) for face in obj.data.polygons],
                "show_wire": obj.show_wire,
                "show_all_edges": obj.show_all_edges,
                "colors": [list(material.diffuse_color) for material in obj.data.materials],
                "node_colors": [
                    list(material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)
                    for material in obj.data.materials
                ],
                "roughness": [
                    material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value
                    for material in obj.data.materials
                ],
            })
        objects[obj.name] = state
    return {
        "scene": bpy.context.scene.name,
        "active": (
            bpy.context.view_layer.objects.active.name
            if bpy.context.view_layer.objects.active else None
        ),
        "collections": {
            collection.name: {
                "objects": sorted(obj.name for obj in collection.objects),
                "children": sorted(child.name for child in collection.children),
            }
            for collection in bpy.data.collections
        },
        "objects": objects,
        "texts": {text.name: text.as_string() for text in bpy.data.texts},
        "views": [
            {
                "shading": area.spaces.active.shading.type,
                "color_type": area.spaces.active.shading.color_type,
                "show_cavity": area.spaces.active.shading.show_cavity,
                "location": list(area.spaces.active.region_3d.view_location),
                "distance": area.spaces.active.region_3d.view_distance,
                "rotation": list(area.spaces.active.region_3d.view_rotation),
                "clip_start": area.spaces.active.clip_start,
                "clip_end": area.spaces.active.clip_end,
            }
            for screen in bpy.data.screens
            for area in screen.areas
            if area.type == "VIEW_3D"
        ],
    }


def assert_close(actual, expected, *, tolerance: float = 1e-6) -> None:
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_close(actual[key], expected[key], tolerance=tolerance)
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected):
            assert_close(actual_item, expected_item, tolerance=tolerance)
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance), (actual, expected)
    else:
        assert actual == expected


def write(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    assert bpy.app.background
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.name = "Q4_Polygonfamilie"
    model_collection = bpy.data.collections.new("Q4_Modell")
    bpy.context.scene.collection.children.link(model_collection)

    root = bpy.data.objects.new("Q4_Gesamtmodell", None)
    model_collection.objects.link(root)
    root.location = Vector((0.5, -0.25, 1.0))
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Quaternion((0.820, 0.425, 0.176, 0.340)).normalized()
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.2
    root["role"] = "model_root"
    root["dimension"] = 4
    root["polygon_count"] = 4
    root["hierarchy"] = "Induktionspfad: links zuerst; 0=Original, 1=Spiegelbild"

    group = bpy.data.objects.new("Schritt_01_0", None)
    model_collection.objects.link(group)
    group.parent = root
    group.empty_display_type = "PLAIN_AXES"
    group.empty_display_size = 0.1
    group["role"] = "construction_group"
    group["construction_path"] = "0"
    models = [
        ("Tetra", [(0, 0, 0), (2, 0, 0), (0, 2, 0), (0, 0, 2)], [],
         [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)]),
        ("Quad", [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], [],
         [(0, 1, 2, 3)]),
        ("Konkav_ä", [(0, 0, 2), (2, 0, 2), (2, 2, 2), (1, 1, 2), (0, 2, 2)], [],
         [(0, 1, 2, 3, 4)]),
        ("Kanten", [(0.1, 0.2, 3.3), (1.1, 0.2, 3.3), (1.1, 1.2, 3.3)],
         [(0, 1), (1, 2)], []),
    ]
    for index, (name, vertices, edges, faces) in enumerate(models):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, edges, faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        model_collection.objects.link(obj)
        obj.parent = group if index else root
        obj["label"] = "Q₄ – " + name
        obj["source_index"] = index
        obj["source_label"] = name
        obj["construction_path"] = format(index, "02b")[::-1]
        obj["graph_bits"] = format(index, "02b")
        obj["vertex_count_numpy"] = len(vertices)
        obj["neighbor_indices_json"] = json.dumps([index ^ 1, index ^ 2])
        obj.location = Vector((0.25, -1.5, 2.0))
        obj.scale = (-1.0, 0.5, 2.0)
        obj.show_wire = True
        obj.show_all_edges = True
        material = bpy.data.materials.new(name + "_Material")
        material.diffuse_color = (0.2, 0.4, 0.8, 1.0)
        material.use_nodes = True
        material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
            0.2, 0.4, 0.8, 1.0
        )
        material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.65
        mesh.materials.append(material)
        obj.color = material.diffuse_color

    source_text = bpy.data.texts.new("NumPy_Quelldaten.json")
    source_text.write('{"schema_version": 1, "label": "Q₄ – Quelle"}')
    readme = bpy.data.texts.new("LIESMICH_Blender")
    readme.write("Hierarchie und ursprüngliche NumPy-Koordinaten bleiben erhalten.\n")

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.shading.type = "SOLID"
                area.spaces.active.shading.color_type = "MATERIAL"
                area.spaces.active.shading.show_cavity = True
                area.spaces.active.region_3d.view_location = Vector((0.0, 0.0, 0.0))
                area.spaces.active.region_3d.view_distance = 8.25
                area.spaces.active.region_3d.view_rotation = Quaternion(
                    (0.820, 0.425, 0.176, 0.340)
                ).normalized()
                area.spaces.active.clip_start = 0.0001
                area.spaces.active.clip_end = 1000.0
    bpy.context.view_layer.objects.active = root
    root.select_set(True)
    bpy.context.preferences.filepaths.save_version = 0
    expected = snapshot()
    assert len(expected["objects"]) == 6
    (folder / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False), encoding="utf-8"
    )
    for compressed in (False, True):
        result = bpy.ops.wm.save_as_mainfile(
            filepath=str((folder / f"model_{compressed}.blend").resolve()),
            compress=compressed,
            check_existing=False,
        )
        assert result == {"FINISHED"}
    print("WRITE_OK", bpy.__file__, bpy.app.version_string)


def read(folder: Path) -> None:
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    for compressed in (False, True):
        result = bpy.ops.wm.open_mainfile(
            filepath=str((folder / f"model_{compressed}.blend").resolve())
        )
        assert result == {"FINISHED"}
        assert_close(snapshot(), expected)
    print("READ_OK", bpy.__file__, bpy.app.version_string)


if __name__ == "__main__":
    mode, directory = sys.argv[1:]
    if mode not in {"write", "read"}:
        raise ValueError("mode must be 'write' or 'read'")
    (write if mode == "write" else read)(Path(directory))
