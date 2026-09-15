#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="/work"
readonly TARGET_PYTHON="/opt/python/cp311-cp311/bin/python"
readonly STAGE_DIR="${WORK_ROOT}/stage/base"
readonly BUILD_DIR="${WORK_ROOT}/build/base"
readonly SOURCE_DIR="${WORK_ROOT}/source/blender"

test -d "${STAGE_DIR}/bpy"
PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" -c \
  'import bpy; print(bpy.__file__); print(bpy.app.version_string)'

PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" \
  "${WORK_ROOT}/tests/verify_blend.py" write "${WORK_ROOT}/reports/baseline-models"
PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" \
  "${WORK_ROOT}/tests/verify_blend.py" read "${WORK_ROOT}/reports/baseline-models"

mkdir -p "${WORK_ROOT}/dist/raw"
"${TARGET_PYTHON}" "${SOURCE_DIR}/build_files/utils/make_bpy_wheel.py" \
  "${STAGE_DIR}" --build-dir "${BUILD_DIR}" --output-dir "${WORK_ROOT}/dist/raw"

wheels=("${WORK_ROOT}"/dist/raw/*.whl)
test "${#wheels[@]}" -eq 1
readonly WHEEL="${wheels[0]}"

"${TARGET_PYTHON}" "${WORK_ROOT}/scripts/analyze_wheel.py" \
  "${WHEEL}" "${WORK_ROOT}/reports/baseline-wheel.json" \
  | tee "${WORK_ROOT}/reports/baseline-wheel.txt"
"${TARGET_PYTHON}" -m auditwheel show "${WHEEL}" \
  | tee "${WORK_ROOT}/reports/auditwheel-show.txt"
