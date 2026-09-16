#!/usr/bin/env bash
set -euo pipefail

# This script is executed in a second container that receives only the wheel,
# tests and these validation helpers.  Source, build and stage trees are not
# mounted and therefore cannot satisfy accidental runtime dependencies.
readonly ROOT="/validation"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly PYTHON="/opt/python/${PYTHON_ABI}/bin/python"
readonly OFFICIAL_PYTHON="/opt/python/cp311-cp311/bin/python"
readonly FINAL_VENV="/tmp/bpy-final-venv"
readonly OFFICIAL_VENV="/tmp/bpy-official-venv"
readonly PYPI_INDEX_URL="${BPY_PYPI_INDEX_URL:-https://pypi.org/simple}"

unset PYTHONPATH
unset LD_LIBRARY_PATH
test -x "${PYTHON}"
wheels=("${ROOT}"/input/*.whl)
test "${#wheels[@]}" -eq 1
readonly WHEEL="${wheels[0]}"

mkdir -p "${ROOT}/reports" "${ROOT}/downloads/numpy"
"${PYTHON}" "${ROOT}/scripts/verify_wheel.py" \
  "${WHEEL}" "${ROOT}/reports/final-wheel-integrity.json"

# Measure the only project-level Python download not already present in a fresh
# environment.  bpy itself declares no third-party Python runtime dependency.
"${PYTHON}" -m pip download --disable-pip-version-check --no-cache-dir \
  --index-url "${PYPI_INDEX_URL}" --only-binary=:all: --no-deps \
  --dest "${ROOT}/downloads/numpy" 'numpy==2.0.2'

"${PYTHON}" -m venv "${FINAL_VENV}"
"${FINAL_VENV}/bin/python" -m pip install --disable-pip-version-check --no-index \
  "${ROOT}"/downloads/numpy/numpy-*.whl
"${FINAL_VENV}/bin/python" -m pip install --disable-pip-version-check \
  --no-deps "${WHEEL}"
"${FINAL_VENV}/bin/python" -m pip check
"${FINAL_VENV}/bin/python" -c \
  'import numpy; import bpy; assert numpy.__version__ == "2.0.2"; print("ISOLATED_IMPORT_OK", bpy.__file__, bpy.app.version_string, numpy.__version__)'

# Minimal writer/reader and repeated exports in one long-lived process.
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  write "${ROOT}/reports/minimal-writer"
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  read "${ROOT}/reports/minimal-writer"
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  multi "${ROOT}/reports/minimal-multi"
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  read "${ROOT}/reports/minimal-multi/first"
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  read "${ROOT}/reports/minimal-multi/second"

# Independent compatibility oracle: the unmodified official Blender wheel.
# The manylinux build image intentionally lacks desktop X11 libraries. They are
# installed only now, after the minimal wheel has proved that it needs none of
# them, so the official wheel can serve as an independent .blend reader/writer.
dnf install -y \
  alsa-lib \
  libICE \
  libSM \
  libX11 \
  libXcursor \
  libXext \
  libXfixes \
  libXi \
  libXinerama \
  libXrandr \
  libXrender \
  libXxf86vm \
  libxkbcommon \
  mesa-libEGL \
  mesa-libGL
"${OFFICIAL_PYTHON}" -m venv "${OFFICIAL_VENV}"
"${OFFICIAL_VENV}/bin/python" -m pip install --disable-pip-version-check \
  --index-url "${PYPI_INDEX_URL}" 'bpy==4.5.3'
"${OFFICIAL_VENV}/bin/python" -m pip check
official_extension="$(find "${OFFICIAL_VENV}" -path '*/site-packages/bpy/__init__.so' -print -quit)"
test -n "${official_extension}"
ldd "${official_extension}" | tee "${ROOT}/reports/official-bpy-ldd.txt"
! grep --quiet 'not found' "${ROOT}/reports/official-bpy-ldd.txt"
"${OFFICIAL_VENV}/bin/python" -c \
  'import bpy; print("OFFICIAL_IMPORT_OK", bpy.__file__, bpy.app.version_string)'
"${OFFICIAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  read "${ROOT}/reports/minimal-writer"
"${OFFICIAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  write "${ROOT}/reports/official-writer"
"${FINAL_VENV}/bin/python" "${ROOT}/tests/verify_blend.py" \
  read "${ROOT}/reports/official-writer"

"${FINAL_VENV}/bin/python" "${ROOT}/scripts/measure_import.py" \
  "${FINAL_VENV}/bin/python" "${ROOT}/reports/import-times.json" \
  --repetitions 5
"${FINAL_VENV}/bin/python" -m pip freeze > "${ROOT}/reports/final-pip-freeze.txt"
"${OFFICIAL_VENV}/bin/python" -m pip freeze > "${ROOT}/reports/official-pip-freeze.txt"
printf '%s\n' "${PYPI_INDEX_URL}" > "${ROOT}/reports/python-package-index.txt"

"${PYTHON}" - "${WHEEL}" "${ROOT}/downloads/numpy" \
  "${ROOT}/reports/download-sizes.json" "${PYPI_INDEX_URL}" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

wheel = Path(sys.argv[1])
numpy_files = list(Path(sys.argv[2]).glob("*.whl"))
assert len(numpy_files) == 1
numpy_wheel = numpy_files[0]
result = {
    "bpy_wheel_bytes": wheel.stat().st_size,
    "bpy_missing_python_dependency_bytes": 0,
    "bpy_total_fresh_environment_download_bytes": wheel.stat().st_size,
    "numpy_2_0_2_wheel": numpy_wheel.name,
    "numpy_2_0_2_bytes": numpy_wheel.stat().st_size,
    "numpy_2_0_2_sha256": sha256(numpy_wheel.read_bytes()).hexdigest(),
    "python_package_index": sys.argv[4],
    "project_total_without_preinstalled_numpy_bytes": (
        wheel.stat().st_size + numpy_wheel.stat().st_size
    ),
    "project_total_with_preinstalled_numpy_bytes": wheel.stat().st_size,
}
Path(sys.argv[3]).write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
PY

"${FINAL_VENV}/bin/python" "${ROOT}/scripts/generate_build_report.py" \
  "${ROOT}/build-reports" "${ROOT}/reports" "${ROOT}/reports"

printf 'ISOLATED_VALIDATION_OK\n'
