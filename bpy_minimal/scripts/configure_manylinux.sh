#!/usr/bin/env bash
set -euo pipefail

# Dieses Skript wird innerhalb des manylinux_2_28_x86_64-Containers ausgeführt.
readonly WORK_ROOT="/work"
readonly BLENDER_SOURCE="${WORK_ROOT}/source/blender"
readonly BUILD_DIR="${WORK_ROOT}/build/base"
readonly STAGE_DIR="${WORK_ROOT}/stage/base"
readonly TARGET_PYTHON="/opt/python/cp311-cp311/bin/python"

test -x "${TARGET_PYTHON}"
test -f "${BLENDER_SOURCE}/CMakeLists.txt"
test -d "${BLENDER_SOURCE}/lib/linux_x64"

"${TARGET_PYTHON}" --version
gcc --version
cmake --version
ninja --version

cmake -S "${BLENDER_SOURCE}" -B "${BUILD_DIR}" -G Ninja \
  -C "${BLENDER_SOURCE}/build_files/cmake/config/bpy_module.cmake" \
  -C "${BLENDER_SOURCE}/build_files/cmake/config/blender_lite.cmake" \
  -C "${WORK_ROOT}/config/mesh_export.cmake" \
  -DPYTHON_VERSION=3.11 \
  -DPYTHON_ROOT_DIR=/opt/python/cp311-cp311 \
  -DCMAKE_INSTALL_PREFIX="${STAGE_DIR}" \
  2>&1 | tee "${WORK_ROOT}/logs/configure-base.log"

# Vor dem Kompilieren werden die tatsächlich aufgelösten Kernoptionen protokolliert.
grep -E '^(PYTHON_VERSION|PYTHON_EXECUTABLE|PYTHON_LIBRARY|WITH_(PYTHON_MODULE|PYTHON_INSTALL|HEADLESS|CYCLES|USD|OPENVDB|MATERIALX|AUDASPACE|OPENCOLORIO)):.*=' \
  "${BUILD_DIR}/CMakeCache.txt" \
  > "${WORK_ROOT}/reports/effective-cmake-options.txt"
