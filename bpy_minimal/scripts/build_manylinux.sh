#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="/work"
readonly BUILD_DIR="${WORK_ROOT}/build/base"

# Vier Prozesse sind der konservative Startwert; bei Speichermangel weiter reduzieren.
cmake --build "${BUILD_DIR}" --parallel "${BPY_BUILD_JOBS:-4}" \
  2>&1 | tee "${WORK_ROOT}/logs/build-base.log"
cmake --install "${BUILD_DIR}" \
  2>&1 | tee "${WORK_ROOT}/logs/install-base.log"
