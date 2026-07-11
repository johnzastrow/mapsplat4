#!/usr/bin/env bash
# Regenerate help/MapSplat_User_Guide.pdf from docs/USER_GUIDE.md (pandoc -> weasyprint).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
CSS="$(mktemp --suffix=.css)"; trap 'rm -f "$CSS" /tmp/_ug.html' EXIT
cat > "$CSS" <<'CSSEOF'
@page { size: letter; margin: 2cm; }
body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 21pt; color: #1b3a5b; border-bottom: 2px solid #1b3a5b; padding-bottom: 4px; }
h2 { font-size: 14pt; color: #1b3a5b; margin-top: 1.3em; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
h3 { font-size: 12pt; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: 9.5pt; }
th, td { border: 1px solid #bbb; padding: 4px 8px; text-align: left; vertical-align: top; }
th { background: #eef2f6; }
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }
a { color: #1b6ec2; text-decoration: none; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.1em 0; }
CSSEOF
mkdir -p help
pandoc docs/USER_GUIDE.md -o /tmp/_ug.html --standalone --embed-resources --css "$CSS" --metadata title="MapSplat User Guide"
uv run --no-project --with weasyprint weasyprint /tmp/_ug.html help/MapSplat_User_Guide.pdf
echo "wrote help/MapSplat_User_Guide.pdf"
