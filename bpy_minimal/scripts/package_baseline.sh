#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="/work"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly TARGET_PYTHON="/opt/python/${PYTHON_ABI}/bin/python"
readonly STAGE_DIR="${WORK_ROOT}/stage/base"
readonly BUILD_DIR="${WORK_ROOT}/build/base"
readonly SOURCE_DIR="${WORK_ROOT}/source/blender"
readonly PACKAGING_PATCH="${WORK_ROOT}/patches/no-unused-runtime-dependencies.patch"

test -d "${STAGE_DIR}/bpy"
PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" -c \
  'import bpy; print(bpy.__file__); print(bpy.app.version_string)'

PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" \
  "${WORK_ROOT}/tests/verify_blend.py" write "${WORK_ROOT}/reports/baseline-models"
PYTHONPATH="${STAGE_DIR}" "${TARGET_PYTHON}" \
  "${WORK_ROOT}/tests/verify_blend.py" read "${WORK_ROOT}/reports/baseline-models"

mkdir -p "${WORK_ROOT}/dist/raw"
if git -C "${SOURCE_DIR}" apply --reverse --check "${PACKAGING_PATCH}" 2>/dev/null; then
  echo "Packaging dependency patch is already applied"
else
  git -C "${SOURCE_DIR}" apply --check "${PACKAGING_PATCH}"
  git -C "${SOURCE_DIR}" apply "${PACKAGING_PATCH}"
fi
SOURCE_DATE_EPOCH=1757335597 \
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

# setuptools writes a second package copy below INSTALL_DIR/build.  Keeping
# that directory would make later pruning appear successful while the final
# wheel silently reused the stale, unpruned baseline payload.
rm -rf -- "${STAGE_DIR}/build" "${STAGE_DIR}/bpy.egg-info"
test ! -e "${STAGE_DIR}/build"
test ! -e "${STAGE_DIR}/bpy.egg-info"
