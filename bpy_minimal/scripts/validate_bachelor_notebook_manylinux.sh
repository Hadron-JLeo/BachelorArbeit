#!/usr/bin/env bash
set -euo pipefail

readonly PYTHON_ABI="${BPY_PYTHON_ABI:?BPY_PYTHON_ABI is required}"
readonly PYTHON="/opt/python/${PYTHON_ABI}/bin/python"
readonly VENV="/tmp/bachelor-notebook-${PYTHON_ABI}"
readonly NOTEBOOK="/repository/Hypercube-graph-bpy-minimal.ipynb"
readonly EXECUTED="/output/Hypercube-graph-bpy-minimal.executed.ipynb"
readonly EXPORT_DIR="/output/blender_export"
readonly BLEND="${EXPORT_DIR}/Q4_Hypercube_Polygonfamilie.blend"
readonly SOURCE_JSON="${EXPORT_DIR}/Q4_Hypercube_Polygonfamilie.json"
readonly INDEX_URL="https://pypi.org/simple"

test -x "${PYTHON}"
test -f "${NOTEBOOK}"
"${PYTHON}" -m venv "${VENV}"
"${VENV}/bin/python" -m pip install --disable-pip-version-check \
  --index-url "${INDEX_URL}" \
  'ipykernel==6.29.5' \
  'nbclient==0.10.2' \
  'nbformat==5.10.4'

"${VENV}/bin/python" \
  /repository/bpy_minimal/scripts/execute_notebook_smoke.py \
  "${NOTEBOOK}" "${EXECUTED}" /output

test -s "${BLEND}"
test -s "${SOURCE_JSON}"
"${VENV}/bin/python" - <<'PY'
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy


blend_path = Path("/output/blender_export/Q4_Hypercube_Polygonfamilie.blend")
json_path = blend_path.with_suffix(".json")
source = json.loads(json_path.read_text(encoding="utf-8"))

assert bpy.ops.wm.open_mainfile(filepath=str(blend_path)) == {"FINISHED"}
assert bpy.context.scene.name == "Q4_Polygonfamilie"
assert "Q4_Modell" in bpy.data.collections

root = bpy.data.objects["Q4_Gesamtmodell"]
assert root.type == "EMPTY"
assert root["role"] == "model_root"
assert root["dimension"] == 4
assert root["polygon_count"] == 16

mesh_objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
empty_objects = [obj for obj in bpy.data.objects if obj.type == "EMPTY"]
assert len(mesh_objects) == 16
assert len(empty_objects) == 15
assert len(bpy.data.materials) == 8
assert sum(len(obj.data.polygons) for obj in mesh_objects) == 16
assert sum(len(obj.data.vertices) for obj in mesh_objects) == 128
assert all(len(obj.data.polygons) == 1 for obj in mesh_objects)
assert all(len(obj.data.vertices) == 8 for obj in mesh_objects)
assert all(len(obj.data.materials) == 1 for obj in mesh_objects)

for record in source["polygons"]:
    path = record["construction_path"]
    obj = bpy.data.objects[f"Polygon_{path}"]
    assert obj["source_index"] == record["index"]
    assert obj["source_label"] == record["label"]
    assert obj["graph_bits"] == record["graph_bits"]
    assert obj["construction_path"] == path
    assert json.loads(obj["neighbor_indices_json"]) == record["neighbor_indices"]
    assert obj.parent.name == f"Schritt_03_{path[:3]}"

    actual_vertices = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    for actual, expected in zip(actual_vertices, record["vertices"]):
        assert all(
            math.isclose(float(actual[axis]), expected[axis], abs_tol=2e-6)
            for axis in range(3)
        ), (obj.name, tuple(actual), expected)

assert "NumPy_Quelldaten.json" in bpy.data.texts
assert "LIESMICH_Blender" in bpy.data.texts
embedded = json.loads(bpy.data.texts["NumPy_Quelldaten.json"].as_string())
assert embedded == source

print(
    "BACHELOR_NOTEBOOK_READER_OK",
    bpy.__file__,
    bpy.app.version_string,
    blend_path.stat().st_size,
)
PY

"${VENV}/bin/python" -m pip check
"${VENV}/bin/python" -m pip freeze --all > /output/bachelor-notebook-pip-freeze.txt
printf '%s\n' "${PYTHON_ABI}" > /output/python-abi.txt
printf '%s\n' "${INDEX_URL}" > /output/python-package-index.txt
printf 'BACHELOR_NOTEBOOK_VALIDATION_OK\n'
