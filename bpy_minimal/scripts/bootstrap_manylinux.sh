#!/usr/bin/env bash
set -euo pipefail

# Dieses Skript ist ausschließlich für den manylinux_2_28_x86_64-Container bestimmt.
readonly WORK_ROOT="/work"
readonly TARGET_PYTHON="/opt/python/cp311-cp311/bin/python"

test -x "${TARGET_PYTHON}"
test -d "${WORK_ROOT}/source/blender/lib/linux_x64"

# Verfügbarkeit zuerst anzeigen; die Paketinstallation bleibt im Container isoliert.
dnf --version
dnf list --available make binutils patch patchelf pkgconf-pkg-config || true
dnf install -y make binutils patch patchelf pkgconf-pkg-config

"${TARGET_PYTHON}" -m pip install \
  'cmake>=3.25,<4' ninja setuptools wheel auditwheel packaging
export PATH="/opt/python/cp311-cp311/bin:${PATH}"

"${TARGET_PYTHON}" --version
gcc --version
git --version
cmake --version
ninja --version
patchelf --version
"${TARGET_PYTHON}" -m pip freeze > "${WORK_ROOT}/reports/build-python-packages.txt"
