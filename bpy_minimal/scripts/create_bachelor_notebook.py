"""Generate the code-only bachelor notebook without visualization dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Hypercube-graph-bpy-minimal.ipynb"


def source(text: str) -> list[str]:
    normalized = dedent(text).strip("\n") + "\n"
    return normalized.splitlines(keepends=True)


def code(cell_id: str, text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {},
        "outputs": [],
        "source": source(text),
    }


cells = [
    code(
        "install-project",
        """
        %pip install --upgrade --no-cache-dir "hypercube-graph-surface @ git+https://github.com/Hadron-JLeo/BachelorArbeit.git@main"
        """,
    ),
    code(
        "select-wheel",
        """
        import hashlib
        import platform
        import sys
        import sysconfig
        from pathlib import Path
        from urllib.request import urlretrieve

        assert sys.platform.startswith("linux"), f"Nur Linux wird unterstützt: {sys.platform}"
        assert platform.machine() in {"x86_64", "AMD64"}, platform.machine()
        libc_name, libc_version = platform.libc_ver()
        assert libc_name == "glibc", (libc_name, libc_version)
        assert tuple(map(int, libc_version.split(".")[:2])) >= (2, 28), libc_version

        python_key = f"{sys.version_info.major}.{sys.version_info.minor}"
        soabi = sysconfig.get_config_var("SOABI")
        assert soabi and soabi.startswith(
            f"cpython-{sys.version_info.major}{sys.version_info.minor}"
        ), soabi

        wheel_names = {
            "3.11": "bpy-4.5.3+mesh1-cp311-cp311-manylinux_2_28_x86_64.whl",
            "3.12": "bpy-4.5.3+mesh1-cp312-cp312-manylinux_2_28_x86_64.whl",
        }
        wheel_hashes = {
            "3.11": "651c74dce5c00b1a822c4ff0d78d6d0cf3904079a78308e171acf28e53629409",
            "3.12": "1f26833ce95fd2c60f42d9f44b34a97326a3a6246d0b3d177d59fb83e99e2ff5",
        }
        if python_key not in wheel_names:
            raise RuntimeError(
                f"Kein geprüftes Wheel für Python {python_key}; "
                f"verfügbar: {sorted(wheel_names)}"
            )

        wheel_name = wheel_names[python_key]
        wheel_url = (
            "https://github.com/Hadron-JLeo/BachelorArbeit/releases/download/"
            f"bpy-mesh-4.5.3.1/{wheel_name}"
        )
        wheel_path = Path("/tmp") / wheel_name
        urlretrieve(wheel_url, wheel_path)
        actual_hash = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
        assert actual_hash == wheel_hashes[python_key]
        print(f"Geprüft: {wheel_path.name} ({wheel_path.stat().st_size / 1_000_000:.1f} MB)")
        """,
    ),
    code(
        "install-wheel",
        """
        %pip install --no-cache-dir --no-deps --force-reinstall {wheel_path}
        """,
    ),
    code(
        "construct-surface",
        """
        from importlib.metadata import version
        import colorsys
        import json
        from numbers import Integral

        import bpy
        from mathutils import Vector
        import numpy as np

        from imports import GeometryConfig, Polygon3D, generate_hypercube_surface

        assert version("hypercube-graph-surface") == "0.1.0"
        assert version("bpy") == "4.5.3+mesh1"
        assert bpy.app.background

        dimension = 4
        geometry_config = GeometryConfig(
            shear_margin=1.0,
            cut_fraction=0.92,
            cut_margin=0.05,
            zero_tolerance=1e-12,
            target_height=1.0,
        )
        surface = generate_hypercube_surface(dimension, config=geometry_config)

        assert len(surface) == 2 ** dimension
        assert all(len(polygon.vertices) == dimension + 4 for polygon in surface)
        assert all(np.isfinite(polygon.vertices).all() for polygon in surface)

        print(f"Q_{dimension}: {len(surface)} Polygone, {len(surface[0].vertices)} Ecken je Polygon")
        """,
    ),
    code(
        "export-functions",
        r'''
        def surface_payload(polygons: list[Polygon3D], dimension: int) -> dict:
            if isinstance(dimension, (bool, np.bool_)) or not isinstance(
                dimension, Integral
            ):
                raise TypeError("dimension muss eine ganze Zahl sein.")
            dimension = int(dimension)
            if dimension < 0 or len(polygons) != 2 ** dimension:
                raise ValueError("Die Polygonzahl muss 2**dimension sein.")
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
                "schema_version": 3,
                "dimension": dimension,
                "coordinate_system": "NumPy x/y/z unverändert",
                "polygons": records,
            }


        def build_blender_scene(data: dict) -> dict:
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
        ''',
    ),
    code(
        "export-execution",
        """
        export_directory = Path.cwd() / "blender_export"
        blend_path = export_directory / f"Q{dimension}_Hypercube_Polygonfamilie.blend"
        blender_export = export_surface_to_blend(
            surface,
            dimension,
            blend_path,
            overwrite=True,
        )

        assert blender_export["mesh_objects"] == 2 ** dimension
        assert blender_export["mesh_faces"] == 2 ** dimension
        assert blender_export["mesh_vertices"] == 2 ** dimension * (dimension + 4)
        assert blender_export["empty_objects"] == 2 ** dimension - 1
        assert len(bpy.data.texts) == 0

        print(f"Blender-Datei: {blender_export['blend_path']}")
        print(f"Quelldaten: {blender_export['json_path']}")
        print(f"Dateigröße: {blender_export['blend_bytes'] / 1_000_000:.2f} MB")
        """,
    ),
    code(
        "download-blend",
        """
        try:
            from google.colab import files

            files.download(str(blend_path))
        except ImportError:
            from IPython.display import FileLink, display

            display(FileLink(str(blend_path)))
        """,
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print(OUTPUT)
