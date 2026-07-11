#!/usr/bin/env bash
# Build the MapSplat QGIS plugin zip for upload to plugins.qgis.org.
# Ships ONLY the plugin source + metadata + LICENSE + install helper. NO docs/ (2.7 MB of images),
# NO go-pmtiles binary and NO shell installers (QGIS/the scanner flag both). The pmtiles CLI is only
# needed for the optional offline-basemap mode; the user installs it (User Guide / in-app link),
# NO compiled resources (the icon loads from a file path). Top-level folder = the package name.
#   Usage: scripts/build_plugin.sh   ->   ./mapsplat.zip
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PLUGIN="mapsplat"; OUT="$ROOT/$PLUGIN.zip"
WORK="$(mktemp -d)"; STAGE="$WORK/$PLUGIN"; trap 'rm -rf "$WORK"' EXIT
mkdir -p "$STAGE"

for f in __init__.py mapsplat.py mapsplat_dockwidget.py exporter.py style_converter.py \
         config_manager.py log_utils.py metadata.txt icon.png LICENSE \
         help/MapSplat_User_Guide.pdf; do
  mkdir -p "$(dirname "$STAGE/$f")"; cp "$ROOT/$f" "$STAGE/$f"
done

find "$STAGE" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

rm -f "$OUT"; ( cd "$WORK" && zip -qr "$OUT" "$PLUGIN" )
LISTING="$(unzip -l "$OUT")"
echo "built $OUT  (version $(grep -E '^version=' metadata.txt | cut -d= -f2))"
for want in mapsplat.py exporter.py style_converter.py LICENSE metadata.txt icon.png; do
  echo "$LISTING" | grep -q "$PLUGIN/$want" || { echo "ERROR: $want missing from zip"; exit 1; }
done
if echo "$LISTING" | grep -qiE "go-pmtiles|\.tar\.gz|__pycache__|resources\.py|/docs/|\.sh$"; then
  echo "ERROR: forbidden entry (binary/cache/docs/shell-script) in zip"; exit 1
fi
echo "OK — source + LICENSE + metadata present; no binaries/docs/cache."
