#!/usr/bin/env bash
set -euo pipefail

# Dieses Skript ist ausschließlich für den manylinux_2_28_x86_64-Container bestimmt.
readonly WORK_ROOT="/work"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly PYTHON_VERSION="${BPY_PYTHON_VERSION:-3.11}"
readonly BUILD_VARIANT="${BPY_BUILD_VARIANT:-standard}"
readonly PYTHON_ROOT="/opt/python/${PYTHON_ABI}"
readonly TARGET_PYTHON="${PYTHON_ROOT}/bin/python"
readonly PYPI_INDEX_URL="${BPY_PYPI_INDEX_URL:-https://pypi.org/simple}"

test -x "${TARGET_PYTHON}"
test -d "${WORK_ROOT}/source/blender/lib/linux_x64"

# Verfügbarkeit zuerst anzeigen; die Paketinstallation bleibt im Container isoliert.
dnf --version
dnf list --available make binutils patch patchelf pkgconf-pkg-config || true
dnf install -y make binutils patch patchelf pkgconf-pkg-config

"${TARGET_PYTHON}" -m pip install --index-url "${PYPI_INDEX_URL}" \
  'auditwheel==6.8.2' \
  'build==1.6.1' \
  'cmake==3.31.10' \
  'ninja==1.13.2' \
  'packaging==26.3' \
  'pyelftools==0.33' \
  'pyproject-hooks==1.2.0' \
  'setuptools==84.0.0' \
  'wheel==0.48.0' \
  'zopfli==0.4.3'
export PATH="${PYTHON_ROOT}/bin:${PATH}"

"${TARGET_PYTHON}" --version
gcc --version
git --version
cmake --version
ninja --version
patchelf --version
"${TARGET_PYTHON}" -m pip freeze --all > "${WORK_ROOT}/reports/build-python-packages.txt"
printf '%s\n' "${PYPI_INDEX_URL}" > "${WORK_ROOT}/reports/python-package-index.txt"
printf '%s\n' "${PYTHON_ABI}" > "${WORK_ROOT}/reports/python-abi.txt"
printf '%s\n' "${PYTHON_VERSION}" > "${WORK_ROOT}/reports/python-version.txt"
printf '%s\n' "${BUILD_VARIANT}" > "${WORK_ROOT}/reports/build-variant.txt"
