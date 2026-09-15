#!/usr/bin/env bash
set -euo pipefail

# Alle Schritte laufen absichtlich im selben kurzlebigen Container.
export PATH="/opt/python/cp311-cp311/bin:${PATH}"

/bin/bash /work/scripts/bootstrap_manylinux.sh
/bin/bash /work/scripts/configure_manylinux.sh
/bin/bash /work/scripts/build_manylinux.sh
/bin/bash /work/scripts/package_baseline.sh
