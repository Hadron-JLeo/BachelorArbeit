#!/usr/bin/env bash
set -euo pipefail

# Alle Schritte laufen absichtlich im selben kurzlebigen Container.
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
export PATH="/opt/python/${PYTHON_ABI}/bin:${PATH}"

/bin/bash -x /work/scripts/bootstrap_manylinux.sh
/bin/bash -x /work/scripts/configure_manylinux.sh
/bin/bash -x /work/scripts/build_manylinux.sh
/bin/bash -x /work/scripts/package_baseline.sh
/bin/bash -x /work/scripts/package_minimal.sh
