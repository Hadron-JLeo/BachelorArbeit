#!/usr/bin/env bash
set -euo pipefail

readonly PYTHON_ABI="${BPY_PYTHON_ABI:?BPY_PYTHON_ABI is required}"
readonly PYTHON="/opt/python/${PYTHON_ABI}/bin/python"
readonly VENV="/tmp/minimal-bpy-notebook"
readonly NOTEBOOK="/repository/bpy_minimal/notebooks/minimal_bpy_colab.ipynb"
readonly EXECUTED="/output/minimal_bpy_colab.executed.ipynb"
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

test -s /output/minimal_bpy_test.blend
"${VENV}/bin/python" - <<'PY'
from pathlib import Path
import math

import bpy

path = Path("/output/minimal_bpy_test.blend")
result = bpy.ops.wm.open_mainfile(filepath=str(path))
assert result == {"FINISHED"}
obj = bpy.data.objects["Dreieck"]
assert [list(vertex.co) for vertex in obj.data.vertices] == [
    [0.0, 0.0, 0.0],
    [2.0, 0.0, 0.0],
    [0.0, 2.0, 0.0],
]
assert [list(face.vertices) for face in obj.data.polygons] == [[0, 1, 2]]
assert obj["quelle"] == "minimal_bpy_colab.ipynb"
expected_color = [
    0.15000000596046448,
    0.3499999940395355,
    0.8999999761581421,
    1.0,
]
assert all(
    math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-7)
    for actual, expected in zip(obj.data.materials[0].diffuse_color, expected_color)
)
print("NOTEBOOK_READER_OK", bpy.__file__, bpy.app.version_string, path.stat().st_size)
PY

"${VENV}/bin/python" -m pip check
"${VENV}/bin/python" -m pip freeze --all > /output/notebook-pip-freeze.txt
printf '%s\n' "${PYTHON_ABI}" > /output/python-abi.txt
printf '%s\n' "${INDEX_URL}" > /output/python-package-index.txt
printf 'NOTEBOOK_VALIDATION_OK\n'
