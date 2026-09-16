#!/usr/bin/env bash
set -euo pipefail

# Dieses Skript ist ausschließlich für den manylinux_2_28_x86_64-Container bestimmt.
readonly WORK_ROOT="/work"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly PYTHON_VERSION="${BPY_PYTHON_VERSION:-3.11}"
readonly BUILD_VARIANT="${BPY_BUILD_VARIANT:-standard}"
readonly PYTHON_ROOT="/opt/python/${PYTHON_ABI}"
readonly TARGET_PYTHON="${PYTHON_ROOT}/bin/python"

test -x "${TARGET_PYTHON}"
test -d "${WORK_ROOT}/source/blender/lib/linux_x64"

# Verfügbarkeit zuerst anzeigen; die Paketinstallation bleibt im Container isoliert.
dnf --version
dnf list --available make binutils patch patchelf pkgconf-pkg-config || true
dnf install -y make binutils patch patchelf pkgconf-pkg-config

"${TARGET_PYTHON}" -m pip install \
  'cmake>=3.25,<4' ninja setuptools wheel auditwheel packaging 'zopfli==0.4.3'
export PATH="${PYTHON_ROOT}/bin:${PATH}"

"${TARGET_PYTHON}" --version
gcc --version
git --version
cmake --version
ninja --version
patchelf --version
"${TARGET_PYTHON}" -m pip freeze > "${WORK_ROOT}/reports/build-python-packages.txt"
printf '%s\n' "${PYTHON_ABI}" > "${WORK_ROOT}/reports/python-abi.txt"
printf '%s\n' "${PYTHON_VERSION}" > "${WORK_ROOT}/reports/python-version.txt"
printf '%s\n' "${BUILD_VARIANT}" > "${WORK_ROOT}/reports/build-variant.txt"
