#!/usr/bin/env bash
set -euo pipefail

# Alle Schritte laufen absichtlich im selben kurzlebigen Container.
export PATH="/opt/python/cp311-cp311/bin:${PATH}"

/bin/bash -x /work/scripts/bootstrap_manylinux.sh
/bin/bash -x /work/scripts/configure_manylinux.sh
/bin/bash -x /work/scripts/build_manylinux.sh
/bin/bash -x /work/scripts/package_baseline.sh
