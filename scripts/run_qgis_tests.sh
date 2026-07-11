#!/usr/bin/env bash
# Run the QGIS-integration tests under QGIS's own Python (QGIS 4.2 / python3.14 here).
# The ordinary `pytest` suite runs without QGIS; these exercise real layers/renderers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export QT_QPA_PLATFORM=offscreen
export MAPSPLAT_QGIS_TEST=1
# QGIS bindings + PyQt6 + the parent dir (so `import mapsplat4.*` resolves)
export PYTHONPATH="/usr/share/qgis/python:/usr/lib/python3/dist-packages:$(dirname "$ROOT"):$ROOT"
cd "$ROOT"
# NB: a segfault in the code under test kills the process (exit 139); judge by the
# unittest OK/FAILED line, not the exit code (QGIS singletons segfault at shutdown).
exec /usr/bin/python3.14 -m unittest test.test_dock_qgis -v
