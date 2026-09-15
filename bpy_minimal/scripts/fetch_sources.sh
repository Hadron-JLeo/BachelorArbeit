#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="${1:-$(pwd)}"
readonly SOURCE_ROOT="${WORK_ROOT}/source/blender"
readonly BLENDER_TAG="v4.5.3"
readonly BLENDER_COMMIT="67807e1800cc48cc7bff3c793525e1179a4d64ca"
readonly LIBRARIES_COMMIT="c1b8027b12441d29b9a344c3f1524d3ce9fa127d"

mkdir -p "${WORK_ROOT}/source" "${WORK_ROOT}/reports" "${WORK_ROOT}/logs"

if [[ ! -d "${SOURCE_ROOT}/.git" ]]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch "${BLENDER_TAG}" \
    https://projects.blender.org/blender/blender.git "${SOURCE_ROOT}"
fi

test "$(git -C "${SOURCE_ROOT}" rev-parse HEAD)" = "${BLENDER_COMMIT}"
git -C "${SOURCE_ROOT}" lfs install --local
GIT_LFS_SKIP_SMUDGE=1 git -C "${SOURCE_ROOT}" submodule update \
  --init --checkout --depth 1 lib/linux_x64
test "$(git -C "${SOURCE_ROOT}/lib/linux_x64" rev-parse HEAD)" = "${LIBRARIES_COMMIT}"
git -C "${SOURCE_ROOT}/lib/linux_x64" lfs pull
git -C "${SOURCE_ROOT}/lib/linux_x64" lfs fsck

git -C "${SOURCE_ROOT}" rev-parse HEAD > "${WORK_ROOT}/reports/blender-commit.txt"
git -C "${SOURCE_ROOT}/lib/linux_x64" rev-parse HEAD \
  > "${WORK_ROOT}/reports/libraries-commit.txt"
git -C "${SOURCE_ROOT}" submodule status > "${WORK_ROOT}/reports/submodules.txt"
