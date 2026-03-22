"""
MapSplat - Exporter Module

This module handles the actual export process:
- Converting layers to GeoPackage
- Generating PMTiles using ogr2ogr
- Converting QGIS styles to MapLibre style JSON
- Generating the HTML viewer
"""

__version__ = "0.6.16"

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

# Windows: hide console window when spawning subprocesses
if sys.platform == "win32":
    # Use numeric values to ensure compatibility
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= 0x00000001  # STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = 0  # SW_HIDE
    CREATIONFLAGS = 0x08000000  # CREATE_NO_WINDOW
else:
    STARTUPINFO = None
    CREATIONFLAGS = 0

from qgis.PyQt.QtCore import QObject, pyqtSignal, QProcess, QTimer

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
)

try:
    from .style_converter import StyleConverter
except ImportError:
    from style_converter import StyleConverter  # test environment (no package)


def generate_html_viewer(settings, style_json, bounds, use_external_style=False, bundle_offline=False):
    """Generate the HTML viewer as a standalone function (no Qt dependencies).

    :param settings: Settings dict; uses ``project_name`` and ``viewer_*`` keys.
                     Unknown/missing viewer keys default to True (control shown).
    :param style_json: Style JSON dict embedded inline (ignored when use_external_style).
    :param bounds: [west, south, east, north] in WGS-84.
    :param use_external_style: If True, reference ./style.json instead of embedding.
    :param bundle_offline: If True, reference local lib/ assets instead of CDN URLs.
    :returns: Complete HTML string for the web viewer.
    """
    center_lng = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2
    project_name = settings.get("project_name", "Map")

    if bundle_offline:
        _assets_comment = "<!-- MapLibre GL JS from local lib/ (bundled for offline use) -->"
        _maplibre_css = '<link rel="stylesheet" href="lib/maplibre-gl.css">'
        _maplibre_js = '<script src="lib/maplibre-gl.js"></script>'
        _pmtiles_js = '<script src="lib/pmtiles.js"></script>'
    else:
        _assets_comment = "<!-- MapLibre GL JS from CDN (replace with local files for offline use) -->"
        _maplibre_css = '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css">'
        _maplibre_js = '<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>'
        _pmtiles_js = '<script src="https://unpkg.com/pmtiles@3.2.0/dist/pmtiles.js"></script>'

    if use_external_style:
        # Fetch style.json at runtime and pass as inline object.
        # Passing './style.json' as a URL string causes MapLibre to normalise
        # source URLs against the style base URL, which prevents pmtiles://
        # sources from being queryable via querySourceFeatures.
        style_ref = "mapStyle"
        _init_open = "\n        fetch('./style.json').then(r => r.json()).then(function(mapStyle) {"
        _init_close = "\n        });"
    else:
        style_ref = json.dumps(style_json, indent=2)
        _init_open = ""
        _init_close = ""

    # ---------- Conditional control snippets ----------
    # Each snippet is an empty string when the control is disabled.
    scale_bar_js = (
        "\n        map.addControl(new maplibregl.ScaleControl(), 'bottom-left');"
        if settings.get('viewer_scale_bar', True) else ""
    )
    geolocate_js = (
        "\n        map.addControl(new maplibregl.GeolocateControl({"
        " positionOptions: { enableHighAccuracy: true },"
        " trackUserLocation: true }), 'top-right');"
        if settings.get('viewer_geolocate', True) else ""
    )
    fullscreen_js = (
        "\n        map.addControl(new maplibregl.FullscreenControl(), 'top-right');"
        if settings.get('viewer_fullscreen', True) else ""
    )

    # Compute top-right offset so custom buttons clear the stacked MapLibre controls.
    # NavigationControl is always added (96 px) + 10 px top margin.
    # FullscreenControl and GeolocateControl each add 39 px (10 px gap + 29 px button)
    # when enabled.  Add 8 px breathing room before our buttons.
    _tr_top = 10 + 96
    if settings.get('viewer_fullscreen', True):
        _tr_top += 39
    if settings.get('viewer_geolocate', True):
        _tr_top += 39
    _tr_top += 8

    # Compute bottom-left offset so custom labels clear the scale bar.
    # MapLibre's ScaleControl is ~22 px tall with a 10 px bottom margin ≈ 32 px.
    # Without scale bar keep a minimal 8 px gap.
    _bl_base = 36 if settings.get('viewer_scale_bar', True) else 8

    coords_html = (
        f'\n    <div id="coords-display"'
        f' style="position:absolute;bottom:{_bl_base + 30}px;left:10px;'
        'background:rgba(255,255,255,0.85);padding:4px 8px;border-radius:3px;'
        'font-family:monospace;font-size:12px;z-index:1;"></div>'
        if settings.get('viewer_coords', True) else ""
    )
    coords_js = (
        "\n        map.on('mousemove', (e) => {"
        " document.getElementById('coords-display').textContent ="
        " e.lngLat.lng.toFixed(5) + ', ' + e.lngLat.lat.toFixed(5); });"
        if settings.get('viewer_coords', True) else ""
    )
    zoom_html = (
        f'\n    <div id="zoom-display"'
        f' style="position:absolute;bottom:{_bl_base}px;left:10px;'
        'background:rgba(255,255,255,0.85);padding:4px 8px;border-radius:3px;'
        'font-family:monospace;font-size:12px;z-index:1;"></div>'
        if settings.get('viewer_zoom_display', True) else ""
    )
    zoom_js = (
        "\n        map.on('zoom', () => {"
        " document.getElementById('zoom-display').textContent ="
        " 'Z: ' + map.getZoom().toFixed(1); });"
        "\n        document.getElementById('zoom-display').textContent ="
        " 'Z: ' + map.getZoom().toFixed(1);"
        if settings.get('viewer_zoom_display', True) else ""
    )
    reset_view_html = (
        f'\n    <button id="reset-view"'
        f' style="position:absolute;top:{_tr_top}px;right:10px;z-index:1;'
        'background:white;border:1px solid #ccc;border-radius:4px;'
        'padding:4px 8px;cursor:pointer;font-size:12px;" title="Reset view">&#8962;</button>'
        if settings.get('viewer_reset_view', True) else ""
    )
    reset_view_js = (
        f"\n        document.getElementById('reset-view').addEventListener('click', () => {{"
        f" map.fitBounds([[{bounds[0]}, {bounds[1]}], [{bounds[2]}, {bounds[3]}]],"
        f" {{ padding: 50 }}); }});"
        if settings.get('viewer_reset_view', True) else ""
    )
    north_reset_html = (
        f'\n    <button id="north-reset"'
        f' style="position:absolute;top:{_tr_top + 37}px;right:10px;z-index:1;'
        'background:white;border:1px solid #ccc;border-radius:4px;'
        'padding:4px 8px;cursor:pointer;font-size:12px;" title="Reset north">N</button>'
        if settings.get('viewer_north_reset', True) else ""
    )
    north_reset_js = (
        "\n        document.getElementById('north-reset').addEventListener('click', () => {"
        " map.setBearing(0); map.setPitch(0); });"
        if settings.get('viewer_north_reset', True) else ""
    )

    # Advanced legend toggle (Python → JS literal)
    _advanced_legend = 'true' if settings.get('advanced_legend') else 'false'

    # Map pixel dimensions — drives the outer container, not the map div itself.
    # All overlay controls are children of the container so they stay clipped.
    map_w = settings.get('map_width', 0)
    map_h = settings.get('map_height', 0)
    if map_w > 0 or map_h > 0:
        w_css = f"{map_w}px" if map_w > 0 else "100%"
        h_css = f"{map_h}px" if map_h > 0 else "100vh"
        container_style = f"position:relative;width:{w_css};height:{h_css};overflow:hidden;"
    else:
        container_style = "position:absolute;top:0;bottom:0;left:0;right:0;"

    # Inline logo SVG (pink blob mark, 28 px, self-contained)
    _logo = (
        '<svg width="28" height="28" viewBox="0 0 127 127" '
        'xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">'
        '<path fill="#cc2e9c" d="m 99.982138,10.210133 c 0.659612,-0.103717 1.689372,-0.09737'
        ' 2.375962,-0.05345 12.90373,0.866775 19.2786,15.42124 11.53345,25.719352'
        ' -6.52171,8.671454 -22.215742,5.478462 -25.802962,16.810831'
        ' -1.59861,5.04958 3.26258,9.245867 8.382,8.02164'
        ' 5.898362,-1.41049 11.230772,-5.93354 17.472032,-4.47119'
        ' 7.70704,1.97035 9.32947,12.204957 3.2758,17.116157'
        ' -8.05338,6.53335 -17.500602,-3.04932 -25.353172,1.74678'
        ' -1.55707,0.94985 -2.65853,2.49449 -3.04905,4.27619'
        ' -0.26221,1.18983 -0.18971,2.76702 0.25135,3.92086'
        ' 2.34262,6.12802 9.28635,5.10064 12.270322,9.87743'
        ' 0.98028,1.56951 1.13427,3.51552 0.65802,5.27288'
        ' -0.53949,1.919547 -1.83172,3.539857 -3.582992,4.493417'
        ' -1.05939,0.57891 -2.25161,0.87074 -3.45864,0.84666'
        ' -6.18331,-0.12197 -8.20552,-8.152337 -14.28908,-9.670517'
        ' -7.27022,-1.81451 -10.15974,4.25503 -8.82227,10.402357'
        ' 0.73422,3.21892 2.44687,6.27063 1.37716,9.63189'
        ' -1.78091,5.59673 -9.542725,6.79212 -13.088935,2.17329'
        ' -2.86094,-3.54409 -0.65484,-7.88141 -0.25479,-11.81841'
        ' 0.49662,-4.883147 -2.03068,-10.564807 -7.88485,-9.294537'
        ' -3.90022,0.8464 -6.8924,4.20502 -8.332,7.811547'
        ' -1.59517,3.99627 -2.68552,8.56668 -7.73668,9.32339'
        ' -1.30042,0.18574 -2.30954,-0.0251 -3.58272,-0.38735'
        ' -2.6199,-1.14697 -4.67968,-3.20781 -4.85881,-6.25448'
        ' -0.44503,-7.571587 7.91316,-8.224307 11.74724,-13.040517'
        ' 2.28097,-2.86465 2.99085,-7.66313 -0.21273,-10.25711'
        ' -4.34102,-3.32607 -9.83191,-0.2995 -13.77844,2.21272'
        ' -3.64702,2.32145 -7.86791,3.75285 -11.74168,0.88661'
        ' -1.9468,-1.44568 -3.05435,-3.40227 -3.3573,-5.82824'
        ' -0.3021497,-2.41802 0.30745,-4.5892 1.84521,-6.50822'
        ' 3.70231,-4.4741 8.54101,-3.00434 13.44136,-2.33442'
        ' 2.04946,0.33047 3.88197,0.17436 5.91741,0.0532'
        ' 5.23584,-0.31167 8.39919,-4.65005 7.62079,-9.782167'
        ' -0.8726,-5.7531 -7.72874,-8.11662 -12.46478,-9.87637'
        ' -1.93332,-0.71834 -4.01109,-1.08585 -5.7748,-2.35558'
        ' -1.8378,-1.33218 -3.07393,-3.337461 -3.43826,-5.577952'
        ' -0.73634,-4.817534 2.11799,-9.337675 7.15195,-9.941454'
        ' 5.77056,-0.69215 7.74409,3.28242 10.86803,7.099035'
        ' 1.388,1.719792 2.98132,3.263106 4.74424,4.595283'
        ' 8.24838,6.130398 14.87382,0.733168 11.77052,-8.661664'
        ' -1.01468,-3.072077 -3.29962,-6.283325 -3.79757,-9.380802'
        ' -0.35163,-2.113227 0.17383,-4.278313 1.45468,-5.995459'
        ' 2.86015,-3.831695 8.09731,-4.381764 11.80042,-1.417108'
        ' 5.211225,4.172479 1.55416,10.110258 2.29394,15.615179'
        ' 0.661975,4.928129 3.441955,8.237538 8.798445,7.408333'
        ' 8.05498,-1.397529 9.96527,-12.032985 12.25418,-18.502576'
        ' 2.74902,-7.770284 6.92441,-12.651846 15.358,-13.905442 z"/>'
        '</svg>'
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - MapSplat</title>
    <!-- <----- BEGIN MAPSPLAT: copy the lines below into your page <head> ----- -->
    {_assets_comment}
    {_maplibre_css}
    {_maplibre_js}
    {_pmtiles_js}
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ margin: 0; }}
        .info-panel {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(255, 255, 255, 0.95);
            padding: 10px 15px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            font-family: sans-serif;
            font-size: 14px;
            z-index: 1;
            max-width: 280px;
        }}
        .info-panel-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .info-panel-header h3 {{
            margin: 0;
            font-size: 16px;
        }}
        .info-panel small {{
            color: #666;
        }}
        .layer-control {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
        }}
        .layer-control h4 {{
            margin: 0 0 8px 0;
            font-size: 13px;
            color: #333;
        }}
        .layer-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
            cursor: pointer;
        }}
        .layer-item input {{
            margin-right: 6px;
            cursor: pointer;
        }}
        .legend-swatch {{
            width: 16px;
            height: 16px;
            min-width: 16px;
            border-radius: 3px;
            margin-right: 6px;
            border: 1px solid rgba(0,0,0,0.2);
        }}
        .legend-swatch.line {{
            height: 4px;
            align-self: center;
        }}
        .legend-swatch.circle {{
            border-radius: 50%;
            width: 12px;
            height: 12px;
            min-width: 12px;
        }}
        .layer-item label {{
            cursor: pointer;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .legend-entries {{ margin: 3px 0 3px 22px; }}
        .legend-entry {{ display: flex; align-items: center; margin: 2px 0; font-size: 11px; color: #555; }}
        .legend-entry .legend-swatch {{ margin-right: 5px; flex-shrink: 0; }}
    </style>
    <!-- <----- END MAPSPLAT <head> section ----- -->
</head>
<body>
    <!-- <----- BEGIN MAPSPLAT: copy the lines below into your page <body> ----- -->
    <!-- NOTE: the CDN <link> and <script> tags from the <head> section above  -->
    <!-- must also be present in your target page for the map to function.      -->
    <div id="map-container" style="{container_style}">
    <div id="map" style="width:100%;height:100%;"></div>
    <div class="info-panel">
        <div class="info-panel-header">
            {_logo}
            <h3>{project_name}</h3>
        </div>
        <small>Generated by MapSplat</small>
        <div class="layer-control">
            <h4>Layers</h4>
            <div id="layer-toggles"></div>
        </div>
    </div>{coords_html}{zoom_html}{reset_view_html}{north_reset_html}
    </div>
    <script>
        // Register PMTiles protocol
        const protocol = new pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", protocol.tile);{_init_open}

        // Initialize map
        const map = new maplibregl.Map({{
            container: 'map',
            style: {style_ref},
            center: [{center_lng}, {center_lat}],
            zoom: 4
        }});

        // Add navigation controls
        map.addControl(new maplibregl.NavigationControl(), 'top-right');{scale_bar_js}{geolocate_js}{fullscreen_js}

        // Fit to data bounds on load and create layer controls
        map.on('load', () => {{
            map.fitBounds([
                [{bounds[0]}, {bounds[1]}],
                [{bounds[2]}, {bounds[3]}]
            ], {{ padding: 50 }});

            // Create layer toggles
            const layerToggles = document.getElementById('layer-toggles');
            const style = map.getStyle();
            // Reverse so top layers appear first in the list (MapLibre renders bottom-to-top)
            const layers = style.layers.filter(l => l['source-layer']).reverse();

            // Unwrap the first literal CSS color from a MapLibre paint expression
            function extractColorFromExpression(expr) {{
                if (typeof expr === 'string') return (expr.startsWith('#') || expr.startsWith('rgb')) ? expr : null;
                if (!Array.isArray(expr)) return null;
                const op = expr[0];
                if (op === 'match') {{
                    // ["match", input, val1, out1, val2, out2, ..., fallback]
                    for (let i = 3; i < expr.length - 1; i += 2) {{
                        if (typeof expr[i] === 'string') return expr[i];
                    }}
                    const fb = expr[expr.length - 1];
                    if (typeof fb === 'string') return fb;
                }} else if (op === 'step') {{
                    // ["step", input, default, stop1, val1, ...]
                    if (typeof expr[2] === 'string') return expr[2];
                }} else if (op === 'interpolate') {{
                    // ["interpolate", interp, input, stop1, val1, ..., capStop, capVal]
                    const vals = [];
                    for (let i = 4; i < expr.length; i += 2) {{
                        if (typeof expr[i] === 'string') vals.push(expr[i]);
                    }}
                    if (vals.length) return vals[Math.floor(vals.length / 2)];
                }}
                for (let i = 1; i < expr.length; i++) {{
                    const found = extractColorFromExpression(expr[i]);
                    if (found) return found;
                }}
                return null;
            }}

            // Helper to extract color from layer paint properties
            function getLayerColor(layer) {{
                const paint = layer.paint || {{}};
                const raw = paint['fill-color'] || paint['line-color'] ||
                            paint['circle-color'] || paint['text-color'] || paint['icon-color'];
                if (!raw) return '#888888';
                return extractColorFromExpression(raw) || '#888888';
            }}

            // Build the main swatch for a layer row (color, shape, or icon)
            function makeLayerSwatch(layer) {{
                const swatch = document.createElement('div');
                swatch.className = 'legend-swatch';
                const color = getLayerColor(layer);
                const ltype = layer.type;
                if (ltype === 'line') {{
                    swatch.classList.add('line');
                    swatch.style.backgroundColor = color;
                }} else if (ltype === 'circle') {{
                    swatch.classList.add('circle');
                    swatch.style.backgroundColor = color;
                }} else if (ltype === 'symbol') {{
                    // Try to render the actual icon from MapLibre's image store
                    const iconName = layer.layout && layer.layout['icon-image'];
                    const iconKey = typeof iconName === 'string' ? iconName : null;
                    let rendered = false;
                    if (iconKey && map.hasImage(iconKey)) {{
                        try {{
                            const img = map.getImage(iconKey);
                            const iw = img.data.width, ih = img.data.height;
                            const pixels = img.data.data;
                            if (iw && ih && pixels) {{
                                const off = document.createElement('canvas');
                                off.width = iw; off.height = ih;
                                off.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(pixels), iw, ih), 0, 0);
                                const c = document.createElement('canvas');
                                c.width = 16; c.height = 16;
                                c.getContext('2d').drawImage(off, 0, 0, 16, 16);
                                swatch.style.cssText = 'background-image:url(' + c.toDataURL() + ');'
                                    + 'background-size:contain;background-repeat:no-repeat;'
                                    + 'background-position:center;background-color:transparent;border:none;'
                                    + 'width:16px;height:16px;min-width:16px;';
                                rendered = true;
                            }}
                        }} catch(e) {{ /* fall through */ }}
                    }}
                    if (!rendered) {{
                        swatch.classList.add('circle');
                        swatch.style.backgroundColor = color || '#888888';
                    }}
                }} else {{
                    // fill or other
                    swatch.style.backgroundColor = color;
                    const outline = layer.paint && layer.paint['fill-outline-color'];
                    if (outline && typeof outline === 'string' && outline !== color) {{
                        swatch.style.borderColor = outline;
                        swatch.style.borderWidth = '2px';
                    }}
                }}
                return swatch;
            }}

            // Build per-class/category legend entries from a layer's paint expression
            function buildLegendEntries(layer) {{
                const paint = layer.paint || {{}};
                const prop = paint['fill-color'] || paint['line-color'] ||
                             paint['circle-color'] || paint['text-color'];
                if (!prop) return [];
                const ltype = layer.type;
                function makeSwatch(color) {{
                    const s = document.createElement('div');
                    // symbol layers are point-like — show as circle in per-category swatches
                    const shapeClass = ltype === 'line' ? ' line'
                        : (ltype === 'circle' || ltype === 'symbol') ? ' circle' : '';
                    s.className = 'legend-swatch' + shapeClass;
                    s.style.backgroundColor = color;
                    return s;
                }}
                function makeEntry(color, label) {{
                    const row = document.createElement('div');
                    row.className = 'legend-entry';
                    row.appendChild(makeSwatch(color));
                    const lbl = document.createElement('span');
                    lbl.textContent = String(label);
                    row.appendChild(lbl);
                    return row;
                }}
                const entries = [];
                if (typeof prop === 'string') {{
                    entries.push(makeEntry(prop, ''));
                }} else if (Array.isArray(prop)) {{
                    const op = prop[0];
                    if (op === 'match') {{
                        for (let i = 2; i < prop.length - 1; i += 2) {{
                            const val = prop[i], color = prop[i + 1];
                            if (typeof color === 'string')
                                entries.push(makeEntry(color, val === '__null__' ? '(no value)' : val));
                        }}
                        const fb = prop[prop.length - 1];
                        if (typeof fb === 'string') entries.push(makeEntry(fb, 'all others'));
                    }} else if (op === 'step') {{
                        if (typeof prop[2] === 'string') entries.push(makeEntry(prop[2], '< ' + prop[3]));
                        for (let i = 3; i < prop.length - 1; i += 2) {{
                            if (typeof prop[i + 1] === 'string') entries.push(makeEntry(prop[i + 1], '\u2265 ' + prop[i]));
                        }}
                    }} else if (op === 'interpolate') {{
                        for (let i = 3; i < prop.length - 1; i += 2) {{
                            if (typeof prop[i + 1] === 'string') entries.push(makeEntry(prop[i + 1], prop[i]));
                        }}
                    }} else {{
                        const c = extractColorFromExpression(prop);
                        if (c) entries.push(makeEntry(c, ''));
                    }}
                }}
                return entries;
            }}

            // Group all layers by source-layer, preserving display order.
            // layers is already reversed so top-rendered layers come first.
            // For each group pick the most representative layer:
            //   fill > line > circle > symbol  (symbol/text is last resort)
            const _pri = {{fill:0, line:1, circle:2, symbol:3}};
            const _slOrder = [], _slGroups = {{}};
            layers.forEach(layer => {{
                const sl = layer['source-layer'];
                if (!_slGroups[sl]) {{ _slGroups[sl] = []; _slOrder.push(sl); }}
                _slGroups[sl].push(layer);
            }});

            _slOrder.forEach(sourceLayer => {{
                const groupLayers = _slGroups[sourceLayer];
                // Pick best representative — lowest priority value wins
                const layer = groupLayers.reduce((best, l) => {{
                    const bp = _pri[best.type] !== undefined ? _pri[best.type] : 99;
                    const lp = _pri[l.type]  !== undefined ? _pri[l.type]  : 99;
                    return lp < bp ? l : best;
                }});

                const div = document.createElement('div');
                div.className = 'layer-item';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = 'toggle-' + sourceLayer;
                checkbox.checked = true;

                const swatch = makeLayerSwatch(layer);

                const label = document.createElement('label');
                label.htmlFor = checkbox.id;
                label.textContent = sourceLayer.replace(/_/g, ' ');
                label.title = sourceLayer;

                checkbox.addEventListener('change', () => {{
                    groupLayers.forEach(l => {{
                        map.setLayoutProperty(l.id, 'visibility',
                            checkbox.checked ? 'visible' : 'none');
                    }});
                }});

                div.appendChild(checkbox);
                div.appendChild(swatch);
                div.appendChild(label);
                layerToggles.appendChild(div);

                if ({_advanced_legend}) {{
                    const entriesDiv = document.createElement('div');
                    entriesDiv.className = 'legend-entries';
                    const entries = buildLegendEntries(layer);
                    entries.forEach(e => entriesDiv.appendChild(e));
                    if (entries.length > 1) div.appendChild(entriesDiv);
                }}
            }});
        }});

        // When the basemap sprite is replaced by the local business sprite, all
        // basemap icon-image keys (shields, POIs, etc.) become missing.  In
        // MapLibre 4.x, unhandled styleimagemissing events stall the symbol
        // rendering queue and prevent business-layer icons from appearing.
        // Adding a transparent 1×1 placeholder immediately unblocks rendering.
        map.on('styleimagemissing', (e) => {{
            if (!map.hasImage(e.id)) {{
                const empty = new ImageData(new Uint8ClampedArray(4), 1, 1);
                map.addImage(e.id, empty);
            }}
        }});

        // Click handler for feature identification
        map.on('click', (e) => {{
            const features = map.queryRenderedFeatures(e.point);
            if (features.length > 0) {{
                const feature = features[0];
                const props = feature.properties;

                let html = '<div style="max-width:300px;max-height:200px;overflow:auto;">';
                for (const [key, value] of Object.entries(props)) {{
                    html += `<strong>${{key}}:</strong> ${{value}}<br>`;
                }}
                html += '</div>';

                new maplibregl.Popup()
                    .setLngLat(e.lngLat)
                    .setHTML(html)
                    .addTo(map);
            }}
        }});

        // Change cursor on feature hover
        map.on('mouseenter', () => {{
            map.getCanvas().style.cursor = 'pointer';
        }});
        map.on('mouseleave', () => {{
            map.getCanvas().style.cursor = '';
        }});{coords_js}{zoom_js}{reset_view_js}{north_reset_js}{_init_close}
    </script>
    <!-- <----- END MAPSPLAT <body> section ----- -->
</body>
</html>'''


class MapSplatExporter(QObject):
    """Handles exporting QGIS layers to web map package."""

    # Signals
    progress = pyqtSignal(int)
    log_message = pyqtSignal(str, str)  # message, level
    finished = pyqtSignal(bool, str)  # success, output_path

    def __init__(self, iface, settings):
        """Initialize exporter.

        :param iface: QGIS interface
        :param settings: Export settings dictionary
        """
        super().__init__()
        self.iface = iface
        self.settings = settings
        self.project = QgsProject.instance()

        # Target CRS (Web Mercator)
        self.target_crs = QgsCoordinateReferenceSystem("EPSG:3857")

        # Cancellation support
        self._cancelled = False
        self._qprocess = None
        self._progress_timer = None
        self._pmtiles_path = None
        self._start_time = None

    def cancel(self):
        """Cancel the export process."""
        self._cancelled = True
        if self._qprocess and self._qprocess.state() != QProcess.NotRunning:
            self._qprocess.kill()
        if self._progress_timer:
            self._progress_timer.stop()

    def run(self):
        """Run the export process."""
        try:
            self._do_export()
        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}", "error")
            self.finished.emit(False, "")

    def _do_export(self):
        """Internal export implementation."""
        output_base = self.settings["output_folder"]
        project_name = self.settings["project_name"]
        output_dir = os.path.join(output_base, f"{project_name}_webmap")

        # Create output directory structure
        self.log_message.emit(f"Creating output directory: {output_dir}", "info")
        self._create_output_structure(output_dir)
        self.progress.emit(10)

        # Get selected layers
        layers = self._get_selected_layers()
        if not layers:
            self.log_message.emit("No valid layers to export", "error")
            self.finished.emit(False, "")
            return

        single_file = self.settings.get("single_file", True)
        style_only = self.settings.get("style_only", False)
        use_basemap = self.settings.get("use_basemap", False)

        # [NEW] Basemap extraction
        if use_basemap and not style_only:
            if not self._check_pmtiles_cli():
                self.log_message.emit(
                    "pmtiles CLI not found. Install it from https://github.com/protomaps/go-pmtiles/releases",
                    "error"
                )
                self.finished.emit(False, "")
                return
            bounds = self._expand_bounds(self._get_bounds(layers))
            self.log_message.emit("Extracting basemap to bounding box...", "info")
            success = self._extract_basemap(output_dir, bounds)
            if not success:
                self.finished.emit(False, "")
                return
            self.progress.emit(30)

        if style_only:
            # Skip data export, just generate style and HTML
            self.log_message.emit("Style-only mode: skipping data export", "info")
            self.progress.emit(60)
        elif single_file:
            # Single PMTiles file containing all layers
            self.log_message.emit("Exporting layers to GeoPackage...", "info")
            gpkg_path = os.path.join(output_dir, "data", "layers.gpkg")
            self._export_to_geopackage(layers["vector"], gpkg_path)
            self.progress.emit(40)

            self.log_message.emit("Converting to PMTiles...", "info")
            pmtiles_path = os.path.join(output_dir, "data", "layers.pmtiles")
            success = self._convert_to_pmtiles(gpkg_path, pmtiles_path)
            if not success:
                self.finished.emit(False, "")
                return
            self.progress.emit(60)

            # Clean up intermediate GeoPackage
            if os.path.exists(gpkg_path):
                os.remove(gpkg_path)
        else:
            # Separate PMTiles file per layer
            self.log_message.emit("Exporting layers separately...", "info")
            total_layers = len(layers["vector"])
            for i, layer in enumerate(layers["vector"]):
                if self._cancelled:
                    self.log_message.emit("Export cancelled.", "warning")
                    self.finished.emit(False, "")
                    return

                layer_name = self._sanitize_layer_name(layer.name())
                self.log_message.emit(f"Processing layer {i+1}/{total_layers}: {layer.name()}", "info")

                # Export single layer to GeoPackage
                gpkg_path = os.path.join(output_dir, "data", f"{layer_name}.gpkg")
                self._export_to_geopackage([layer], gpkg_path)

                # Convert to PMTiles
                pmtiles_path = os.path.join(output_dir, "data", f"{layer_name}.pmtiles")
                success = self._convert_to_pmtiles(gpkg_path, pmtiles_path)
                if not success:
                    self.log_message.emit(f"Failed to convert {layer_name}", "error")
                    # Continue with other layers instead of aborting
                    continue

                # Clean up intermediate GeoPackage
                if os.path.exists(gpkg_path):
                    os.remove(gpkg_path)

                # Update progress (10-60% range for conversion)
                progress = 10 + int(50 * (i + 1) / total_layers)
                self.progress.emit(progress)

            self.progress.emit(60)

        # Convert styles
        self.log_message.emit("Converting styles...", "info")
        style_converter = StyleConverter(
            layers["vector"],
            self.settings,
            log_callback=lambda msg: self.log_message.emit(msg, "info"),
        )
        style_json = style_converter.convert(
            single_file=single_file,
            output_dir=output_dir if not style_only else None,
        )

        # Handle style merging
        if use_basemap:
            basemap_style_path = self.settings.get("basemap_style_path", "")
            self.log_message.emit("Merging business layers into basemap style...", "info")
            style_json = self._merge_business_into_basemap(basemap_style_path, style_json)
        elif self.settings.get("imported_style_path"):
            style_json = self._merge_imported_style(style_json)

        self.progress.emit(75)

        # Write style.json if requested
        if self.settings["export_style_json"]:
            style_path = os.path.join(output_dir, "style.json")
            with open(style_path, "w", encoding="utf-8") as f:
                json.dump(style_json, f, indent=2)
            self.log_message.emit(f"Wrote style.json", "info")

        # Download/copy MapLibre assets first so HTML can reference local paths
        bundle_offline = self._copy_maplibre_assets(output_dir)

        # Generate HTML viewer
        self.log_message.emit("Generating HTML viewer...", "info")
        self._generate_html_viewer(output_dir, style_json, layers, bundle_offline=bundle_offline)
        self.progress.emit(90)

        # Write README and serve script
        self._write_readme(output_dir)
        self._write_serve_script(output_dir)
        self.progress.emit(100)

        self.log_message.emit("Export complete!", "success")
        self.finished.emit(True, output_dir)

    def _create_output_structure(self, output_dir):
        """Create the output directory structure."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(output_dir, "data")).mkdir(exist_ok=True)
        Path(os.path.join(output_dir, "lib")).mkdir(exist_ok=True)

    def _get_selected_layers(self):
        """Get the selected layers from the project.

        :returns: Dictionary with 'vector' and 'raster' layer lists
        """
        layers = {"vector": [], "raster": []}

        for layer_id in self.settings["layer_ids"]:
            layer = self.project.mapLayer(layer_id)
            if layer is None:
                continue

            if isinstance(layer, QgsVectorLayer):
                layers["vector"].append(layer)
            elif isinstance(layer, QgsRasterLayer):
                layers["raster"].append(layer)

        return layers

    def _export_to_geopackage(self, layers, gpkg_path):
        """Export vector layers to a GeoPackage.

        :param layers: List of QgsVectorLayer
        :param gpkg_path: Output GeoPackage path
        """
        transform_context = QgsCoordinateTransformContext()

        for i, layer in enumerate(layers):
            layer_name = self._sanitize_layer_name(layer.name())
            self.log_message.emit(f"  Exporting: {layer.name()} -> {layer_name}", "info")

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer_name
            options.fileEncoding = "UTF-8"

            # Set action mode (create or append)
            if i == 0:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            else:
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            # Transform to Web Mercator
            if layer.crs() != self.target_crs:
                options.ct = QgsCoordinateTransform(
                    layer.crs(),
                    self.target_crs,
                    self.project
                )

            error, error_message, new_filename, new_layer = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                gpkg_path,
                transform_context,
                options
            )

            if error != QgsVectorFileWriter.NoError:
                self.log_message.emit(f"  Warning: {error_message}", "warning")

    def _convert_to_pmtiles(self, gpkg_path, pmtiles_path):
        """Convert GeoPackage to PMTiles using ogr2ogr (blocking version for thread).

        :param gpkg_path: Input GeoPackage path
        :param pmtiles_path: Output PMTiles path
        :returns: True if successful
        """
        import time
        from qgis.PyQt.QtCore import QCoreApplication

        # Check GDAL version first
        gdal_version = self._check_gdal_version()
        if gdal_version:
            self.log_message.emit(f"  GDAL version: {gdal_version}", "info")

        # Check if PMTiles driver is available
        if not self._check_pmtiles_driver():
            self.log_message.emit(
                "PMTiles driver not available. GDAL 3.8+ required.",
                "error"
            )
            return False

        # Show input file size
        gpkg_size_mb = os.path.getsize(gpkg_path) / (1024 * 1024)
        self.log_message.emit(f"  GeoPackage size: {gpkg_size_mb:.1f} MB", "info")

        # List layers in GeoPackage
        layers_in_gpkg = self._list_gpkg_layers(gpkg_path)
        if layers_in_gpkg:
            self.log_message.emit(f"  Layers to convert: {', '.join(layers_in_gpkg)}", "info")
        else:
            self.log_message.emit("  Warning: Could not list layers in GeoPackage", "warning")

        # Normalize paths for Windows
        gpkg_path = os.path.normpath(gpkg_path)
        pmtiles_path = os.path.normpath(pmtiles_path)
        output_dir = os.path.dirname(pmtiles_path)

        # Build ogr2ogr command
        max_zoom = self.settings.get("max_zoom", 6)

        self.log_message.emit(f"  Max zoom: {max_zoom}", "info")
        self.log_message.emit(f"  Output: {pmtiles_path}", "info")
        self.log_message.emit("  Starting ogr2ogr (this runs in background)...", "info")

        # Use QProcess for non-blocking execution
        self._qprocess = QProcess()
        self._pmtiles_path = pmtiles_path
        self._output_dir = output_dir
        self._start_time = time.time()

        args = [
            "-f", "PMTiles",
            "-dsco", "MINZOOM=0",
            "-dsco", f"MAXZOOM={max_zoom}",
            "-t_srs", "EPSG:3857",
            pmtiles_path,
            gpkg_path
        ]

        self.log_message.emit(f"  Command: ogr2ogr {' '.join(args)}", "info")

        # Start process
        self._qprocess.start("ogr2ogr", args)

        if not self._qprocess.waitForStarted(5000):
            self.log_message.emit("  Failed to start ogr2ogr", "error")
            return False

        self.log_message.emit("  ogr2ogr started, waiting for completion...", "info")

        # Poll with event processing to keep UI responsive
        last_update = time.time()
        while self._qprocess.state() != QProcess.NotRunning:
            # Process Qt events to keep UI responsive
            QCoreApplication.processEvents()

            # Check for cancellation
            if self._cancelled:
                self._qprocess.kill()
                self._qprocess.waitForFinished(1000)
                self.log_message.emit("  Export cancelled by user.", "warning")
                return False

            # Update progress every 3 seconds
            now = time.time()
            if now - last_update >= 3:
                last_update = now
                elapsed = now - self._start_time
                if os.path.exists(pmtiles_path):
                    size_mb = os.path.getsize(pmtiles_path) / (1024 * 1024)
                    self.log_message.emit(f"  Processing... {elapsed:.0f}s, output: {size_mb:.1f} MB", "info")
                else:
                    self.log_message.emit(f"  Processing... {elapsed:.0f}s (building tiles)", "info")

            # Small sleep to avoid busy loop
            self._qprocess.waitForFinished(100)

        # Process finished
        elapsed = time.time() - self._start_time
        exit_code = self._qprocess.exitCode()
        stderr = bytes(self._qprocess.readAllStandardError()).decode('utf-8', errors='replace')
        stdout = bytes(self._qprocess.readAllStandardOutput()).decode('utf-8', errors='replace')

        self.log_message.emit(f"  Conversion finished in {elapsed:.1f} seconds", "info")

        if exit_code != 0:
            error_msg = stderr.strip() if stderr.strip() else stdout.strip()
            if not error_msg:
                error_msg = f"ogr2ogr exited with code {exit_code}"
            self.log_message.emit(f"  ogr2ogr error: {error_msg}", "error")
            return False

        # Show output file size
        if os.path.exists(pmtiles_path):
            pmtiles_size_mb = os.path.getsize(pmtiles_path) / (1024 * 1024)
            self.log_message.emit(f"  PMTiles size: {pmtiles_size_mb:.1f} MB", "info")

        return True

    def _check_gdal_version(self):
        """Check GDAL version.

        :returns: Version string or None
        """
        try:
            result = subprocess.run(
                ["ogr2ogr", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=STARTUPINFO,
                creationflags=CREATIONFLAGS
            )
            if result.returncode == 0:
                # Parse "GDAL 3.8.0, released 2023/..."
                return result.stdout.split(",")[0].strip()
        except Exception:
            pass
        return None

    def _check_pmtiles_driver(self):
        """Check if PMTiles driver is available.

        :returns: True if available
        """
        try:
            result = subprocess.run(
                ["ogr2ogr", "--formats"],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=STARTUPINFO,
                creationflags=CREATIONFLAGS
            )
            return "PMTiles" in result.stdout
        except Exception:
            return False

    def _list_gpkg_layers(self, gpkg_path):
        """List layers in a GeoPackage.

        :param gpkg_path: Path to GeoPackage
        :returns: List of layer names or empty list
        """
        try:
            result = subprocess.run(
                ["ogrinfo", "-so", "-q", gpkg_path],
                capture_output=True,
                text=True,
                timeout=30,
                startupinfo=STARTUPINFO,
                creationflags=CREATIONFLAGS
            )
            if result.returncode == 0:
                # Parse output like "1: layer_name (Multi Polygon)"
                layers = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        # Extract layer name between ": " and " ("
                        parts = line.split(": ", 1)
                        if len(parts) > 1:
                            layer_name = parts[1].split(" (")[0]
                            layers.append(layer_name)
                return layers
        except Exception:
            pass
        return []

    def _merge_imported_style(self, style_json):
        """Merge imported style with generated style.

        :param style_json: Generated style dictionary
        :returns: Merged style dictionary
        """
        import_path = self.settings["imported_style_path"]
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported = json.load(f)

            # Merge layers from imported style (imported takes precedence)
            imported_layer_ids = {l["id"] for l in imported.get("layers", [])}
            for layer in style_json.get("layers", []):
                if layer["id"] not in imported_layer_ids:
                    imported.setdefault("layers", []).append(layer)

            self.log_message.emit("Merged imported style", "info")
            return imported

        except Exception as e:
            self.log_message.emit(f"Failed to merge style: {e}", "warning")
            return style_json

    def _check_pmtiles_cli(self):
        """Check if the pmtiles CLI is available.

        :returns: True if pmtiles CLI is found and functional
        """
        try:
            result = subprocess.run(
                ["pmtiles", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=STARTUPINFO,
                creationflags=CREATIONFLAGS
            )
            return result.returncode == 0
        except Exception:
            return False

    def _extract_basemap(self, output_dir, bounds):
        """Run pmtiles extract to clip basemap to data bounding box.

        :param output_dir: Export output directory
        :param bounds: [west, south, east, north] in EPSG:4326
        :returns: True if successful
        """
        import time
        from qgis.PyQt.QtCore import QCoreApplication

        source = self.settings["basemap_source"]
        output_path = os.path.join(output_dir, "data", "basemap.pmtiles")
        west, south, east, north = bounds
        bbox_str = f"{west},{south},{east},{north}"
        max_zoom = self.settings.get("max_zoom", 10)

        self.log_message.emit(f"  Basemap source: {source}", "info")
        self.log_message.emit(f"  Bounding box: {bbox_str}", "info")
        self.log_message.emit(f"  Max zoom: {max_zoom}", "info")
        self.log_message.emit(f"  Output: {output_path}", "info")

        args = [
            "extract",
            source,
            output_path,
            f"--bbox={bbox_str}",
            f"--maxzoom={max_zoom}",
        ]

        self.log_message.emit(f"  Command: pmtiles {' '.join(args)}", "info")

        self._qprocess = QProcess()
        self._start_time = time.time()

        self._qprocess.start("pmtiles", args)

        if not self._qprocess.waitForStarted(10000):
            self.log_message.emit("  Failed to start pmtiles", "error")
            return False

        self.log_message.emit("  pmtiles extract started, waiting...", "info")

        last_update = time.time()
        while self._qprocess.state() != QProcess.NotRunning:
            QCoreApplication.processEvents()

            if self._cancelled:
                self._qprocess.kill()
                self._qprocess.waitForFinished(1000)
                self.log_message.emit("  Export cancelled by user.", "warning")
                return False

            now = time.time()
            if now - last_update >= 3:
                last_update = now
                elapsed = now - self._start_time
                if os.path.exists(output_path):
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    self.log_message.emit(
                        f"  Extracting... {elapsed:.0f}s, output: {size_mb:.1f} MB", "info"
                    )
                else:
                    self.log_message.emit(
                        f"  Extracting... {elapsed:.0f}s", "info"
                    )

            self._qprocess.waitForFinished(100)

        elapsed = time.time() - self._start_time
        exit_code = self._qprocess.exitCode()
        stderr = bytes(self._qprocess.readAllStandardError()).decode("utf-8", errors="replace")
        stdout = bytes(self._qprocess.readAllStandardOutput()).decode("utf-8", errors="replace")

        self.log_message.emit(f"  pmtiles extract finished in {elapsed:.1f}s", "info")

        if exit_code != 0:
            error_msg = stderr.strip() or stdout.strip() or f"pmtiles exited with code {exit_code}"
            self.log_message.emit(f"  pmtiles error: {error_msg}", "error")
            return False

        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            self.log_message.emit(f"  Basemap PMTiles size: {size_mb:.1f} MB", "info")

        return True

    def _merge_business_into_basemap(self, basemap_style_path, business_style_json):
        """Merge business layer sources and styles on top of a basemap style.

        The basemap's remote tile URL is replaced with the local extracted file.
        Business layer sources are injected and layers appended (background excluded).
        When the business style has a sprite, it overrides the basemap's sprite so
        that business icons always render from the local file (reliable offline).

        :param basemap_style_path: Path to Protomaps basemap style.json
        :param business_style_json: Style dict generated from QGIS layers
        :returns: Merged style dictionary
        """
        try:
            with open(basemap_style_path, "r", encoding="utf-8") as f:
                basemap = json.load(f)
        except Exception as e:
            self.log_message.emit(f"Failed to load basemap style: {e}", "error")
            return business_style_json

        # Update basemap's vector tile source URL to point to local extracted file.
        # Match any vector source that has a URL (not just Protomaps-hosted ones),
        # so locally-sourced basemaps (e.g. pmtiles://maine4.pmtiles) are rewritten too.
        for src_name, src in basemap.get("sources", {}).items():
            if src.get("type") == "vector" and src.get("url"):
                src["url"] = "pmtiles://data/basemap.pmtiles"
                self.log_message.emit(
                    f"  Updated basemap source '{src_name}' to local file", "info"
                )
                break

        # Inject business data sources
        basemap.setdefault("sources", {}).update(business_style_json.get("sources", {}))

        # Append business layers, skipping background (basemap provides its own)
        overlay_layers = [
            layer for layer in business_style_json.get("layers", [])
            if layer.get("id") != "background"
        ]
        basemap.setdefault("layers", []).extend(overlay_layers)

        self.log_message.emit(
            f"  Merged {len(overlay_layers)} business layer(s) into basemap style", "info"
        )

        # Handle sprites — always use the local business sprite directly.
        # Multi-sprite arrays with remote basemap URLs are unreliable when the remote
        # sprite is slow or unreachable; the local sprite is guaranteed to be present.
        # Basemap icon-image layers (shields, arrows, POIs) will silently render no icon,
        # but all fill/line/water/label layers continue to render normally.
        business_sprite = business_style_json.get("sprite")

        if business_sprite:
            basemap["sprite"] = business_sprite
            self.log_message.emit(
                "  Using local business sprite for icons", "info"
            )

        return basemap


    def _generate_html_viewer(self, output_dir, style_json, layers, bundle_offline=False):
        """Generate the HTML viewer file.

        :param output_dir: Output directory
        :param style_json: Style JSON dictionary
        :param layers: Dictionary of layers
        :param bundle_offline: If True, reference local lib/ assets instead of CDN
        """
        # Calculate viewer bounds from extent layer (or data) — no expansion here;
        # MapLibre's fitBounds padding keeps the view slightly inset from the bounds.
        bounds = self._get_bounds(layers)

        # If exporting style.json, reference it externally instead of embedding
        use_external_style = self.settings.get("export_style_json", False)
        html_content = self._get_html_template(style_json, bounds, use_external_style, bundle_offline)
        html_path = os.path.join(output_dir, "index.html")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _get_bounds(self, layers):
        """Return bounds for the export, honouring the extent-layer setting.

        If ``extent_layer_id`` is set in settings and the layer exists, its
        extent is used; otherwise falls back to the combined data extent.

        :param layers: Dict with 'vector' list (fallback when no extent layer).
        :returns: [west, south, east, north] in EPSG:4326
        """
        extent_id = self.settings.get("extent_layer_id")
        if extent_id:
            layer = self.project.mapLayer(extent_id)
            if layer:
                self.log_message.emit(
                    f"Using extent of '{layer.name()}' for export bounds", "info"
                )
                return self._calculate_bounds([layer])
            else:
                self.log_message.emit(
                    "Extent layer not found in project — using full data extent", "warning"
                )
        return self._calculate_bounds(layers["vector"])

    @staticmethod
    def _expand_bounds(bounds, pct=0.005):
        """Expand [W, S, E, N] bounds by *pct* fraction on every side.

        A 0.5 % expansion (pct=0.005) adds a small buffer so that basemap
        tiles are not clipped exactly at the data edge.
        """
        west, south, east, north = bounds
        dw = (east - west) * pct
        dh = (north - south) * pct
        return [west - dw, south - dh, east + dw, north + dh]

    def _calculate_bounds(self, layers):
        """Calculate combined bounds of all layers.

        :param layers: List of layers
        :returns: [west, south, east, north] in EPSG:4326
        """
        if not layers:
            return [-180, -85, 180, 85]

        combined = None
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")

        for layer in layers:
            extent = layer.extent()

            # Transform to WGS84
            if layer.crs() != crs_4326:
                transform = QgsCoordinateTransform(
                    layer.crs(),
                    crs_4326,
                    QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)

            if combined is None:
                combined = extent
            else:
                combined.combineExtentWith(extent)

        if combined:
            return [
                combined.xMinimum(),
                combined.yMinimum(),
                combined.xMaximum(),
                combined.yMaximum()
            ]

        return [-180, -85, 180, 85]

    def _get_html_template(self, style_json, bounds, use_external_style=False, bundle_offline=False):
        """Get the HTML template.

        :param style_json: Style JSON dictionary
        :param bounds: [west, south, east, north]
        :param use_external_style: If True, reference ./style.json instead of embedding
        :param bundle_offline: If True, reference local lib/ assets instead of CDN
        :returns: HTML string
        """
        return generate_html_viewer(self.settings, style_json, bounds, use_external_style, bundle_offline)

    def _copy_maplibre_assets(self, output_dir):
        """Download MapLibre JS/CSS assets to lib/ for offline use if requested.

        :param output_dir: Output directory containing lib/
        :returns: True if assets were downloaded successfully, False if CDN should be used.
        """
        if not self.settings.get("bundle_offline", False):
            self.log_message.emit("  Using CDN for MapLibre assets", "info")
            return False

        assets = [
            ("https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css", "maplibre-gl.css"),
            ("https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js", "maplibre-gl.js"),
            ("https://unpkg.com/pmtiles@3.2.0/dist/pmtiles.js", "pmtiles.js"),
        ]

        lib_dir = os.path.join(output_dir, "lib")
        try:
            import urllib.request
            for url, filename in assets:
                dest = os.path.join(lib_dir, filename)
                self.log_message.emit(f"  Downloading {filename}...", "info")
                urllib.request.urlretrieve(url, dest)
            self.log_message.emit("  MapLibre assets bundled for offline use", "success")
            return True
        except Exception as e:
            self.log_message.emit(
                f"  Warning: could not download MapLibre assets ({e}); falling back to CDN",
                "warning",
            )
            return False

    def _write_readme(self, output_dir):
        """Write README file with deployment instructions.

        :param output_dir: Output directory
        """
        readme_content = f'''# {self.settings["project_name"]} - Web Map

Generated by MapSplat QGIS Plugin

## Contents

- `index.html` - Main web map viewer
- `data/layers.pmtiles` - Vector tile data
- `style.json` - MapLibre style (if exported)
- `lib/` - JavaScript libraries

## Deployment

1. Upload this entire folder to any web server that supports HTTP Range Requests
2. Ensure CORS is configured if hosting on a different domain
3. Open index.html in a browser

### Supported Hosting

- Any static web server (nginx, Apache, Caddy)
- Cloud storage (AWS S3, Cloudflare R2, Google Cloud Storage)
- GitHub Pages
- Netlify, Vercel, etc.

### CORS Configuration

If hosting PMTiles on a different domain, configure CORS headers:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD
Access-Control-Allow-Headers: Range
Access-Control-Expose-Headers: Content-Range, Content-Length
```

## Offline Use

For fully offline operation, download MapLibre GL JS:
- https://unpkg.com/maplibre-gl/dist/maplibre-gl.js
- https://unpkg.com/maplibre-gl/dist/maplibre-gl.css
- https://unpkg.com/pmtiles/dist/pmtiles.js

Place these files in the `lib/` folder.

## Credits

- Generated by MapSplat (https://github.com/johnzastrow/mqs)
- Uses MapLibre GL JS (https://maplibre.org/)
- Uses PMTiles (https://protomaps.com/docs/pmtiles)
'''
        readme_path = os.path.join(output_dir, "README.txt")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

    def _write_serve_script(self, output_dir):
        """Write a simple Python server script for local viewing.

        :param output_dir: Output directory
        """
        serve_script = '''#!/usr/bin/env python3
"""
HTTP server with Range request support for PMTiles.

Usage:
    python serve.py                           # start on port 8000, open browser
    python serve.py --port 8001               # use a different port
    python serve.py --no-browser              # don't open the browser (server mode)
    python serve.py --host 0.0.0.0            # bind to all interfaces (LAN / direct VPS access)

Press Ctrl+C to stop the server (or close this window).
"""

import argparse
import http.server
import os
import signal
import socketserver
import sys
import threading
import webbrowser

parser = argparse.ArgumentParser(description="MapSplat local map server")
parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
parser.add_argument("--host", default="127.0.0.1",
                    help="Address to bind to (default: 127.0.0.1; use 0.0.0.0 for LAN or direct VPS access)")
parser.add_argument("--no-browser", action="store_true", help="Do not open the browser on startup")
args = parser.parse_args()

PORT = args.port
HOST = args.host
server_running = True


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Multi-threaded HTTP server — handles concurrent requests."""
    daemon_threads = True


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with support for Range requests (required for PMTiles)."""

    server_version = "MapSplat"
    sys_version = ""

    def version_string(self):
        """Hide server implementation details."""
        return self.server_version

    def log_error(self, format, *args):
        """Suppress connection aborted errors (normal when browser cancels requests)."""
        if "ConnectionAbortedError" not in str(args):
            super().log_error(format, *args)

    def handle(self):
        """Handle requests, silently ignoring connection aborts."""
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Browser cancelled the request, this is normal

    def send_head(self):
        """Handle HEAD requests and Range requests."""
        path = self.translate_path(self.path)

        if os.path.isdir(path):
            index = os.path.join(path, "index.html")
            if os.path.exists(index):
                path = index
            else:
                self.send_error(403, "Directory listing not allowed")
                return None

        if not os.path.exists(path):
            self.send_error(404, "File not found")
            return None

        file_size = os.path.getsize(path)

        # Check for Range header
        range_header = self.headers.get("Range")

        if range_header:
            # Parse Range header — supports single ranges only.
            # Examples: "bytes=0-1023", "bytes=1024-", "bytes=-500" (last 500 bytes)
            try:
                if not range_header.startswith("bytes="):
                    raise ValueError("unsupported range unit")
                range_spec = range_header[6:]  # strip "bytes="
                if "," in range_spec:
                    raise ValueError("multi-range not supported")
                start_str, end_str = range_spec.split("-", 1)
                # Suffix range: "bytes=-N" means the last N bytes
                if start_str == "":
                    suffix_len = int(end_str)
                    start = max(0, file_size - suffix_len)
                    end = file_size - 1
                else:
                    start = int(start_str)
                    end = int(end_str) if end_str else file_size - 1
                end = min(end, file_size - 1)
                if start < 0 or start > end:
                    raise ValueError(f"invalid range {start}-{end}")
                length = end - start + 1

                self.send_response(206)  # Partial Content
                self.send_header("Content-Type", self.guess_type(path))
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                f = open(path, "rb")
                try:
                    f.seek(start)
                    return _FileWrapper(f, length)
                except Exception:
                    f.close()
                    raise
            except (ValueError, OSError):
                self.send_error(416, "Range Not Satisfiable")
                return None
        else:
            # Normal request
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return open(path, "rb")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range")
        self.end_headers()


class _FileWrapper:
    """Wrapper to read a specific byte range from a file."""
    def __init__(self, f, length):
        self.f = f
        self.remaining = length

    def read(self, size=None):
        if self.remaining <= 0:
            return b""
        if size is None or size > self.remaining:
            size = self.remaining
        data = self.f.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()


def shutdown_server(signum=None, frame=None):
    """Handle shutdown signal."""
    global server_running
    server_running = False
    print("\\nShutting down server...")
    httpd.shutdown()
    print("Server stopped.")
    sys.exit(0)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

    print(f"Starting server at http://localhost:{PORT}")
    if HOST != "127.0.0.1":
        print(f"  (listening on {HOST}:{PORT})")
    print("Press Ctrl+C to stop (or close this window)\\n")

    httpd = ThreadingHTTPServer((HOST, PORT), RangeRequestHandler)

    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, shutdown_server)
    signal.signal(signal.SIGTERM, shutdown_server)
    # Windows-specific: handle Ctrl+Break
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown_server)

    # Run server in a daemon thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    if not args.no_browser:
        webbrowser.open(f"http://localhost:{PORT}")

    try:
        # Keep main thread alive with a simple loop
        while server_running:
            server_thread.join(timeout=0.5)
            if not server_thread.is_alive():
                break
    except KeyboardInterrupt:
        shutdown_server()
'''
        serve_path = os.path.join(output_dir, "serve.py")
        with open(serve_path, "w", encoding="utf-8") as f:
            f.write(serve_script)

    def _sanitize_layer_name(self, name):
        """Sanitize layer name for use in files/PMTiles.

        :param name: Original layer name
        :returns: Sanitized name
        """
        # Replace spaces and special chars with underscores
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        # Remove consecutive underscores
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")
        # Ensure lowercase for consistency
        return sanitized.lower()
