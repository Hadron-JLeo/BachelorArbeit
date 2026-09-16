#!/usr/bin/env bash
set -euo pipefail

# Dieses Skript wird innerhalb des manylinux_2_28_x86_64-Containers ausgeführt.
readonly WORK_ROOT="/work"
readonly BLENDER_SOURCE="${WORK_ROOT}/source/blender"
readonly BUILD_DIR="${WORK_ROOT}/build/base"
readonly STAGE_DIR="${WORK_ROOT}/stage/base"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly PYTHON_VERSION="${BPY_PYTHON_VERSION:-3.11}"
readonly CONFIG_PROFILE="${BPY_CONFIG_PROFILE:-mesh_export.cmake}"
readonly PYTHON_ROOT="/opt/python/${PYTHON_ABI}"
readonly TARGET_PYTHON="${PYTHON_ROOT}/bin/python"
readonly PYTHON_LIBRARY_STUB="/tmp/bpy-python-module-link/libpython${PYTHON_VERSION}.a"

test -x "${TARGET_PYTHON}"
test -f "${BLENDER_SOURCE}/CMakeLists.txt"
test -d "${BLENDER_SOURCE}/lib/linux_x64"
test -f "${WORK_ROOT}/config/${CONFIG_PROFILE}"
test -f "${PYTHON_ROOT}/include/python${PYTHON_VERSION}/Python.h"

# manylinux intentionally does not ship libpython, and a Python extension must
# not link it. Blender's finder nevertheless requires a library path before it
# notices WITH_PYTHON_MODULE. An empty archive satisfies configuration; any
# accidental link against it would still fail and expose the mistake.
mkdir -p "$(dirname "${PYTHON_LIBRARY_STUB}")"
ar rcs "${PYTHON_LIBRARY_STUB}"

"${TARGET_PYTHON}" --version
gcc --version
cmake --version
ninja --version

cmake -S "${BLENDER_SOURCE}" -B "${BUILD_DIR}" -G Ninja \
  -C "${BLENDER_SOURCE}/build_files/cmake/config/bpy_module.cmake" \
  -C "${BLENDER_SOURCE}/build_files/cmake/config/blender_lite.cmake" \
  -C "${WORK_ROOT}/config/${CONFIG_PROFILE}" \
  -DPYTHON_VERSION="${PYTHON_VERSION}" \
  -DPYTHON_ROOT_DIR="${PYTHON_ROOT}" \
  -DPYTHON_EXECUTABLE="${TARGET_PYTHON}" \
  -DPYTHON_INCLUDE_DIR="${PYTHON_ROOT}/include/python${PYTHON_VERSION}" \
  -DPYTHON_INCLUDE_CONFIG_DIR="${PYTHON_ROOT}/include/python${PYTHON_VERSION}" \
  -DPYTHON_LIBRARY="${PYTHON_LIBRARY_STUB}" \
  -DPYTHON_LIBPATH="${PYTHON_ROOT}/lib" \
  -DCMAKE_INSTALL_PREFIX="${STAGE_DIR}" \
  2>&1 | tee "${WORK_ROOT}/logs/configure-base.log"

# Vor dem Kompilieren werden die tatsächlich aufgelösten Kernoptionen protokolliert.
grep -E '^(PYTHON_VERSION|PYTHON_EXECUTABLE|PYTHON_LIBRARY|WITH_(PYTHON_MODULE|PYTHON_INSTALL|HEADLESS|OPENGL_BACKEND|CYCLES|USD|OPENVDB|MATERIALX|AUDASPACE|OPENCOLORIO|LINKER_GOLD)):.*=' \
  "${BUILD_DIR}/CMakeCache.txt" \
  > "${WORK_ROOT}/reports/effective-cmake-options.txt"
