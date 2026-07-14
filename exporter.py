"""
MapSplat - Exporter Module

This module handles the actual export process:
- Converting layers to GeoPackage
- Generating PMTiles using ogr2ogr
- Converting QGIS styles to MapLibre style JSON
- Generating the HTML viewer
"""

__version__ = "0.13.0"

import os
import sys
import json
import base64
import shutil
import subprocess
import datetime
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

from qgis.PyQt.QtCore import QObject, pyqtSignal, QProcess

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsRectangle,
)

try:
    from qgis.core import QgsVectorTileLayer
except ImportError:  # older QGIS without vector tile layers
    QgsVectorTileLayer = None

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
        _maplibre_css = '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css">'
        _maplibre_js = '<script src="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js"></script>'
        _pmtiles_js = '<script src="https://unpkg.com/pmtiles@4.4.1/dist/pmtiles.js"></script>'

    # Both paths expose the style as a local `mapStyle` object so the sprite URL can be
    # rewritten to absolute before the map is created (MapLibre GL JS 5.x REJECTS a relative
    # sprite URL like "./sprites" — it must be absolute).
    _sprite_fixup = (
        "\n        (function(){"
        "\n            var abs = function(u){ return /^https?:\\/\\//.test(u) ? u"
        "                : new URL(u, window.location.href).href; };"
        "\n            if (Array.isArray(mapStyle.sprite)) {"
        "\n                mapStyle.sprite.forEach(function(s){ if (s && s.url) s.url = abs(s.url); });"
        "\n            } else if (mapStyle.sprite) {"
        "\n                mapStyle.sprite = abs(mapStyle.sprite);"
        "\n            }"
        "\n        })();"
    )
    if use_external_style:
        # Fetch style.json at runtime and pass as inline object.
        # Passing './style.json' as a URL string causes MapLibre to normalise
        # source URLs against the style base URL, which prevents pmtiles://
        # sources from being queryable via querySourceFeatures.
        style_ref = "mapStyle"
        _init_open = ("\n        fetch('./style.json').then(r => r.json()).then(function(mapStyle) {"
                      + _sprite_fixup)
        _init_close = "\n        });"
    else:
        style_ref = "mapStyle"
        _init_open = ("\n        const mapStyle = " + json.dumps(style_json, indent=2) + ";"
                      + _sprite_fixup)
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
    attribution_text = settings.get('attribution', '').strip()
    if attribution_text:
        _attribution_escaped = attribution_text.replace("'", "\\'")
        attribution_js = (
            f"\n        map.addControl(new maplibregl.AttributionControl({{ compact: true,"
            f" customAttribution: '{_attribution_escaped}' }}), 'bottom-right');"
        )
    else:
        attribution_js = ""

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
    # Shared look for all custom map buttons — 29x29 (matches MapLibre's control buttons, e.g.
    # the geolocate "find my location" button), white background, black line-art icon.
    _btn_css = ('position:absolute;right:10px;z-index:1;width:29px;height:29px;padding:0;'
                'display:flex;align-items:center;justify-content:center;color:#000;background:#fff;'
                'border:none;border-radius:4px;box-shadow:0 0 0 2px rgba(0,0,0,0.1);cursor:pointer;')
    # Line-art icons (stroke=currentColor so they invert to white when a button is active).
    _svg_open = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">')
    _ICON_RESET = _svg_open + '<path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 0-2-2v-3"/></svg>'
    _ICON_NORTH = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" '
                   'stroke-width="1" stroke-linejoin="round"><path d="M12 2l6 19-6-4-6 4z"/></svg>')
    _ICON_MEASURE = _svg_open + '<rect x="2" y="8" width="20" height="8" rx="1"/><path d="M6 8v3M10 8v4M14 8v3M18 8v4"/></svg>'
    _ICON_DRAW = _svg_open + '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>'
    _ICON_EXPORT = _svg_open + '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>'

    reset_view_html = (
        f'\n    <button id="reset-view" style="{_btn_css}top:{_tr_top}px;" title="Reset view">{_ICON_RESET}</button>'
        if settings.get('viewer_reset_view', True) else ""
    )
    reset_view_js = (
        f"\n        document.getElementById('reset-view').addEventListener('click', () => {{"
        f" map.fitBounds([[{bounds[0]}, {bounds[1]}], [{bounds[2]}, {bounds[3]}]],"
        f" {{ padding: 50 }}); }});"
        if settings.get('viewer_reset_view', True) else ""
    )
    north_reset_html = (
        f'\n    <button id="north-reset" style="{_btn_css}top:{_tr_top + 37}px;" title="Reset north">{_ICON_NORTH}</button>'
        if settings.get('viewer_north_reset', True) else ""
    )
    north_reset_js = (
        "\n        document.getElementById('north-reset').addEventListener('click', () => {"
        " map.setBearing(0); map.setPitch(0); });"
        if settings.get('viewer_north_reset', True) else ""
    )

    # ---------- Interactive map tools (plugin framework) ----------
    # Tools are self-registering plugin objects that talk to the map through a small, stable
    # surface (the MapSplatTools ctx). They only use long-stable MapLibre APIs (addSource/addLayer,
    # getCanvas, on/once, controls), so upgrading the MapLibre library does not touch the tools.
    _measure_on = settings.get('viewer_measure', False)
    _draw_on = settings.get('viewer_draw', False)
    _export_on = settings.get('viewer_export', False)
    _tools_any = _measure_on or _draw_on or _export_on
    # Author-set defaults; the viewer can change both at runtime.
    _measure_units = settings.get('measure_units', 'both')
    if _measure_units not in ('both', 'metric', 'imperial'):
        _measure_units = 'both'
    _draw_color = settings.get('draw_color', '#1d6fe0')
    if not (isinstance(_draw_color, str) and _draw_color.startswith('#') and len(_draw_color) == 7):
        _draw_color = '#1d6fe0'
    # preserveDrawingBuffer is required to read pixels back from the WebGL canvas (export tool),
    # but has a rendering cost — only enable it when the export tool is on.
    _preserve_buffer = 'true' if _export_on else 'false'
    # Paint a scale bar into exported images when the on-screen scale bar is enabled (WYSIWYG).
    _export_scalebar = 'true' if settings.get('viewer_scale_bar', True) else 'false'
    _tools_top = _tr_top + 74  # first tool button sits below the native control stack

    _framework_js = """
        // ===== MapSplat tool host — version-agnostic plugin framework =====
        window.MapSplatTools = (function () {
            const tools = [], deactivators = {};
            let map = null, slot = __TOP__;
            const container = () => document.getElementById('map-container') || document.body;
            const ctx = {
                get map() { return map; },
                addButton(opts) {
                    const b = document.createElement('button');
                    b.innerHTML = opts.icon; b.title = opts.title || '';
                    // 29x29 to match MapLibre's native control buttons (e.g. geolocate), white bg,
                    // black line-art icon centred; stroke=currentColor lets it invert when active.
                    b.style.cssText = 'position:absolute;right:10px;z-index:1;width:29px;height:29px;padding:0;'
                        + 'display:flex;align-items:center;justify-content:center;color:#000;background:#fff;border:none;'
                        + 'border-radius:4px;box-shadow:0 0 0 2px rgba(0,0,0,0.1);cursor:pointer;top:' + slot + 'px;';
                    b._top = slot; slot += 37;
                    container().appendChild(b);
                    if (opts.onClick) b.addEventListener('click', () => opts.onClick(b));
                    return b;
                },
                makePanel(refBtn, extra) {
                    const p = document.createElement('div');
                    p.style.cssText = 'position:absolute;right:50px;z-index:2;display:none;background:rgba(255,255,255,0.96);'
                        + 'border:1px solid #ccc;border-radius:4px;padding:6px;font-family:sans-serif;font-size:12px;'
                        + 'box-shadow:0 1px 4px rgba(0,0,0,0.2);top:' + refBtn._top + 'px;' + (extra || '');
                    container().appendChild(p);
                    return p;
                },
                mkBtn(label, title) {
                    const b = document.createElement('button');
                    b.innerHTML = label; if (title) b.title = title;
                    b.style.cssText = 'display:inline-block;margin:2px;padding:3px 6px;border:1px solid #ccc;'
                        + 'border-radius:3px;background:#fff;cursor:pointer;font-size:12px;';
                    return b;
                },
                setActive(btn, on, color) { btn.style.background = on ? (color || '#e0245e') : '#fff'; btn.style.color = on ? '#fff' : '#000'; },
                download(blob, filename) {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = filename; document.body.appendChild(a); a.click();
                    document.body.removeChild(a); setTimeout(() => URL.revokeObjectURL(url), 1000);
                },
                registerDeactivator(name, fn) { deactivators[name] = fn; },
                activateExclusive(name) { for (const k in deactivators) if (k !== name) try { deactivators[k](); } catch (e) {} },
                freshCanvas(cb) { map.once('render', () => cb(map.getCanvas())); map.triggerRepaint(); }
            };
            return {
                register(t) { tools.push(t); },
                install(m) { map = m; tools.forEach(t => { try { t.setup(map, ctx); } catch (e) { console.error('MapSplat tool ' + t.id, e); } }); },
                _tools: tools, _ctx: ctx
            };
        })();""".replace('__TOP__', str(_tools_top))

    _measure_reg = ("""
        // ----- Measure plugin -----
        MapSplatTools.register({ id: 'measure', setup(map, ctx) {
            const R = 6371008.8, SRC = 'mapsplat-measure';
            let measuring = false, pts = [], finished = false, units = '__UNITS__';
            const btn = ctx.addButton({ icon: '__ICON__', title: 'Measure distance & area', onClick: () => setMode(!measuring) });
            const readout = ctx.makePanel(btn, 'top:auto;bottom:40px;right:10px;max-width:250px;line-height:1.35;');
            const fc = (f) => ({ type: 'FeatureCollection', features: f });
            function ensureLayers() {
                if (map.getSource(SRC)) return;
                map.addSource(SRC, { type: 'geojson', data: fc([]) });
                map.addLayer({ id: SRC + '-fill', type: 'fill', source: SRC, filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': '#e0245e', 'fill-opacity': 0.12 } });
                map.addLayer({ id: SRC + '-line', type: 'line', source: SRC, filter: ['==', '$type', 'LineString'], paint: { 'line-color': '#e0245e', 'line-width': 2, 'line-dasharray': [2, 1] } });
                map.addLayer({ id: SRC + '-pts', type: 'circle', source: SRC, filter: ['==', '$type', 'Point'], paint: { 'circle-radius': 4, 'circle-color': '#fff', 'circle-stroke-color': '#e0245e', 'circle-stroke-width': 2 } });
            }
            function haversine(a, b) { const t = Math.PI / 180, dLat = (b[1]-a[1])*t, dLon = (b[0]-a[0])*t; const h = Math.sin(dLat/2)**2 + Math.cos(a[1]*t)*Math.cos(b[1]*t)*Math.sin(dLon/2)**2; return 2*R*Math.asin(Math.sqrt(h)); }
            function pathLength(c, close) { let d = 0; for (let i = 1; i < c.length; i++) d += haversine(c[i-1], c[i]); if (close && c.length >= 3) d += haversine(c[c.length-1], c[0]); return d; }
            function ringArea(c) { if (c.length < 3) return 0; const t = Math.PI / 180, r = c.concat([c[0]]); let s = 0; for (let i = 0; i < r.length - 1; i++) { const p1 = r[i], p2 = r[i+1]; s += (p2[0]-p1[0])*t * (2 + Math.sin(p1[1]*t) + Math.sin(p2[1]*t)); } return Math.abs(s*R*R/2); }
            function fmtLen(m) { const met = m < 1000 ? m.toFixed(1) + ' m' : (m/1000).toFixed(2) + ' km'; const mi = m/1609.344, ft = m*3.28084; const imp = mi < 0.5 ? ft.toFixed(0) + ' ft' : mi.toFixed(2) + ' mi'; return units === 'metric' ? met : units === 'imperial' ? imp : met + '  /  ' + imp; }
            function fmtArea(m2) { const km2 = m2/1e6, ha = m2/1e4; const met = m2 < 1e4 ? m2.toFixed(0) + ' m\\u00B2' : (km2 < 1 ? ha.toFixed(2) + ' ha' : km2.toFixed(2) + ' km\\u00B2'); const ac = m2/4046.8564, mi2 = m2/2.58999e6, ft2 = m2*10.7639; const imp = ac < 1 ? ft2.toFixed(0) + ' ft\\u00B2' : (mi2 < 1 ? ac.toFixed(2) + ' ac' : mi2.toFixed(2) + ' mi\\u00B2'); return units === 'metric' ? met : units === 'imperial' ? imp : met + '  /  ' + imp; }
            function unitLabel() { return units === 'both' ? 'metric + imperial' : units; }
            function cycleUnits() { units = units === 'both' ? 'metric' : units === 'metric' ? 'imperial' : 'both'; updateReadout(); }
            function updateReadout() {
                let html = '<div style="text-align:right;margin-bottom:3px;"><span id="mm-units" style="cursor:pointer;text-decoration:underline;opacity:.7;" title="Click to change units">' + unitLabel() + '</span></div>';
                if (pts.length >= 2) html += '<div><b>Length:</b> ' + fmtLen(pathLength(pts, finished && pts.length >= 3)) + '</div>';
                if (finished && pts.length >= 3) html += '<div><b>Area:</b> ' + fmtArea(ringArea(pts)) + '</div>';
                if (!pts.length) html += '<div>Click the map to add points.</div>';
                else if (!finished) html += '<div style="opacity:.65;margin-top:3px;">Right-click to finish \\u00B7 Esc to clear</div>';
                else html += '<div style="opacity:.65;margin-top:3px;">Click to start a new measurement \\u00B7 Esc to clear</div>';
                readout.innerHTML = html;
                const u = document.getElementById('mm-units'); if (u) u.onclick = cycleUnits;
            }
            function render() { ensureLayers(); const f = pts.map(p => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: p } })); if (pts.length >= 2) f.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: pts } }); if (finished && pts.length >= 3) f.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [pts.concat([pts[0]])] } }); map.getSource(SRC).setData(fc(f)); updateReadout(); }
            function clearAll() { pts = []; finished = false; if (map.getSource(SRC)) map.getSource(SRC).setData(fc([])); updateReadout(); }
            function setMode(on) { measuring = on; ctx.setActive(btn, on, '#e0245e'); readout.style.display = on ? 'block' : 'none'; map.getCanvas().style.cursor = on ? 'crosshair' : ''; if (on) { ctx.activateExclusive('measure'); map.doubleClickZoom.disable(); ensureLayers(); updateReadout(); } else { map.doubleClickZoom.enable(); clearAll(); } window.__mapsplatToolActive = on; }
            ctx.registerDeactivator('measure', () => setMode(false));
            map.on('click', (e) => { if (!measuring) return; if (finished) { pts = []; finished = false; } pts.push([e.lngLat.lng, e.lngLat.lat]); render(); });
            map.on('contextmenu', (e) => { if (!measuring) return; if (e.originalEvent) e.originalEvent.preventDefault(); if (pts.length >= 2) { finished = true; render(); } });
            document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && measuring) clearAll(); });
            window.__mapsplatMeasure = { setMode, addPoint: (lng, lat) => { if (finished) { pts = []; finished = false; } pts.push([lng, lat]); render(); }, finish: () => { if (pts.length >= 2) { finished = true; render(); } }, setUnits: (u) => { units = u; updateReadout(); }, readEl: () => readout, length: () => pathLength(pts, finished && pts.length >= 3), area: () => (finished && pts.length >= 3 ? ringArea(pts) : 0) };
        }});""".replace('__UNITS__', _measure_units).replace('__ICON__', _ICON_MEASURE)) if _measure_on else ""

    _draw_reg = ("""
        // ----- Draw / sketch plugin -----
        MapSplatTools.register({ id: 'draw', setup(map, ctx) {
            const SRC = 'mapsplat-draw', DEFAULT = '__COLOR__';
            let active = false, mode = 'point', color = DEFAULT, features = [], pending = [];
            const btn = ctx.addButton({ icon: '__ICON__', title: 'Draw & export', onClick: () => setActive(!active) });
            const panel = ctx.makePanel(btn, 'width:158px;');
            const fc = (f) => ({ type: 'FeatureCollection', features: f });
            const feat = (type, coords) => ({ type: 'Feature', properties: { color: color }, geometry: { type: type, coordinates: coords } });
            function ensureLayers() {
                if (map.getSource(SRC)) return;
                map.addSource(SRC, { type: 'geojson', data: fc([]) });
                const c = ['coalesce', ['get', 'color'], DEFAULT];
                map.addLayer({ id: SRC + '-fill', type: 'fill', source: SRC, filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': c, 'fill-opacity': 0.15 } });
                map.addLayer({ id: SRC + '-line', type: 'line', source: SRC, filter: ['==', '$type', 'LineString'], paint: { 'line-color': c, 'line-width': 2.5 } });
                map.addLayer({ id: SRC + '-pts', type: 'circle', source: SRC, filter: ['==', '$type', 'Point'], paint: { 'circle-color': c, 'circle-radius': 5, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
            }
            function render() { ensureLayers(); const shown = features.slice(); if (pending.length === 1 && mode !== 'point') shown.push({ type: 'Feature', properties: { color: color }, geometry: { type: 'Point', coordinates: pending[0] } }); else if (pending.length >= 2 && (mode === 'line' || mode === 'polygon')) shown.push({ type: 'Feature', properties: { color: color }, geometry: { type: 'LineString', coordinates: pending } }); map.getSource(SRC).setData(fc(shown)); }
            function commitPending() { if (mode === 'line' && pending.length >= 2) features.push(feat('LineString', pending.slice())); else if (mode === 'polygon' && pending.length >= 3) features.push(feat('Polygon', [pending.concat([pending[0]])])); pending = []; render(); }
            function addVertex(lng, lat) { if (mode === 'point') { features.push(feat('Point', [lng, lat])); render(); } else { pending.push([lng, lat]); render(); } }
            function undo() { if (pending.length) pending.pop(); else if (features.length) features.pop(); render(); }
            function clearAll() { features = []; pending = []; if (map.getSource(SRC)) map.getSource(SRC).setData(fc([])); }
            function toGeoJSON() { return JSON.stringify(fc(features), null, 2); }
            function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
            function coordStr(cs) { return cs.map(c => c[0] + ',' + c[1] + ',0').join(' '); }
            function kmlColor(hex) { const h = (hex || DEFAULT).replace('#', ''); return 'ff' + h.slice(4, 6) + h.slice(2, 4) + h.slice(0, 2); }
            function toKML() {
                let out = '<?xml version="1.0" encoding="UTF-8"?>\\n<kml xmlns="http://www.opengis.net/kml/2.2">\\n<Document>\\n<name>MapSplat drawing</name>\\n';
                features.forEach((f, i) => {
                    const g = f.geometry, kc = kmlColor(f.properties && f.properties.color);
                    out += '<Placemark><name>' + esc(g.type + ' ' + (i + 1)) + '</name>';
                    out += '<Style><LineStyle><color>' + kc + '</color><width>2</width></LineStyle><PolyStyle><color>' + kc.replace('ff', '80') + '</color></PolyStyle></Style>';
                    if (g.type === 'Point') out += '<Point><coordinates>' + g.coordinates[0] + ',' + g.coordinates[1] + ',0</coordinates></Point>';
                    else if (g.type === 'LineString') out += '<LineString><coordinates>' + coordStr(g.coordinates) + '</coordinates></LineString>';
                    else if (g.type === 'Polygon') out += '<Polygon><outerBoundaryIs><LinearRing><coordinates>' + coordStr(g.coordinates[0]) + '</coordinates></LinearRing></outerBoundaryIs></Polygon>';
                    out += '</Placemark>\\n';
                });
                return out + '</Document>\\n</kml>\\n';
            }
            function refreshModes() { ['point', 'line', 'polygon'].forEach(m => { const b = panel.querySelector('[data-mode="' + m + '"]'); if (b) { b.style.background = (m === mode) ? color : '#fff'; b.style.color = (m === mode) ? '#fff' : '#000'; } }); }
            function buildPanel() {
                if (panel.dataset.built) return; panel.dataset.built = '1';
                const r1 = document.createElement('div');
                [['point', 'Point'], ['line', 'Line'], ['polygon', 'Poly']].forEach(([m, lbl]) => { const b = ctx.mkBtn(lbl, m + ' mode'); b.dataset.mode = m; b.onclick = () => { mode = m; pending = []; render(); refreshModes(); }; r1.appendChild(b); });
                const rc = document.createElement('div'); rc.style.margin = '3px 2px'; const lab = document.createElement('label'); lab.textContent = 'Colour '; lab.style.fontSize = '12px';
                const col = document.createElement('input'); col.type = 'color'; col.value = DEFAULT; col.style.verticalAlign = 'middle'; col.oninput = () => { color = col.value; refreshModes(); render(); }; lab.appendChild(col); rc.appendChild(lab);
                const r2 = document.createElement('div'); const fB = ctx.mkBtn('Finish', 'Finish line/polygon'); fB.onclick = commitPending; const uB = ctx.mkBtn('Undo'); uB.onclick = undo; const cB = ctx.mkBtn('Clear'); cB.onclick = clearAll; r2.append(fB, uB, cB);
                const r3 = document.createElement('div'); r3.style.marginTop = '3px'; const gj = ctx.mkBtn('\\u2b07 GeoJSON'); gj.onclick = () => ctx.download(new Blob([toGeoJSON()], { type: 'application/geo+json' }), 'mapsplat-drawing.geojson'); const km = ctx.mkBtn('\\u2b07 KML'); km.onclick = () => ctx.download(new Blob([toKML()], { type: 'application/vnd.google-earth.kml+xml' }), 'mapsplat-drawing.kml'); r3.append(gj, km);
                panel.append(r1, rc, r2, r3); refreshModes();
            }
            function setActive(on) { active = on; ctx.setActive(btn, on, DEFAULT); panel.style.display = on ? 'block' : 'none'; map.getCanvas().style.cursor = on ? 'crosshair' : ''; if (on) { ctx.activateExclusive('draw'); map.doubleClickZoom.disable(); ensureLayers(); buildPanel(); } else { map.doubleClickZoom.enable(); pending = []; render(); } window.__mapsplatToolActive = on; }
            ctx.registerDeactivator('draw', () => setActive(false));
            map.on('click', (e) => { if (active) addVertex(e.lngLat.lng, e.lngLat.lat); });
            map.on('contextmenu', (e) => { if (active && mode !== 'point') { if (e.originalEvent) e.originalEvent.preventDefault(); commitPending(); } });
            document.addEventListener('keydown', (ev) => { if (!active) return; if (ev.key === 'Escape') { pending = []; render(); } else if (ev.key === 'Enter') commitPending(); });
            window.__mapsplatDraw = { setActive, setMode: (m) => { mode = m; pending = []; }, setColor: (c) => { color = c; }, addPoint: addVertex, finish: commitPending, count: () => features.length, toGeoJSON, toKML };
        }});""".replace('__COLOR__', _draw_color).replace('__ICON__', _ICON_DRAW)) if _draw_on else ""

    _export_reg = ("""
        // ----- Print / export plugin -----
        MapSplatTools.register({ id: 'export', setup(map, ctx) {
            const SCALEBAR = __SCALEBAR__;
            const btn = ctx.addButton({ icon: '__ICON__', title: 'Export map image (JPG / PDF)', onClick: () => { panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'block' : 'none'; } });
            const panel = ctx.makePanel(btn, 'white-space:nowrap;');
            const jpgB = ctx.mkBtn('JPG'); const pdfB = ctx.mkBtn('PDF');
            const note = document.createElement('div'); note.textContent = 'map + drawings' + (SCALEBAR ? ' + scale bar' : ''); note.style.cssText = 'opacity:.6;font-size:11px;margin-top:2px;';
            panel.append(jpgB, pdfB, note);
            function stamp() { const d = new Date(), p = (n) => String(n).padStart(2, '0'); return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds()); }
            function b64ToBytes(dataUrl) { const b64 = dataUrl.split(',')[1]; const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
            // Nice round number for a scale bar (matches MapLibre's ScaleControl heuristic).
            function roundNum(num) { const p = Math.pow(10, ('' + Math.floor(num)).length - 1); let d = num / p; d = d >= 10 ? 10 : d >= 5 ? 5 : d >= 3 ? 3 : d >= 2 ? 2 : 1; return p * d; }
            function drawScaleBar(g, W, H) {
                if (!SCALEBAR) return;
                try {
                    const dpr = (map.getCanvas().width / map.getContainer().clientWidth) || 1;
                    const maxCss = 100, yy = map.getContainer().clientHeight - 1;
                    const a = map.unproject([0, yy]), b = map.unproject([maxCss, yy]);
                    const maxM = a.distanceTo(b); if (!isFinite(maxM) || maxM <= 0) return;
                    const dist = roundNum(maxM), barW = maxCss * (dist / maxM) * dpr;
                    const label = dist >= 1000 ? (dist / 1000) + ' km' : dist + ' m';
                    const x0 = 10 * dpr, baseY = H - 12 * dpr;
                    g.save();
                    g.font = Math.round(11 * dpr) + 'px sans-serif'; g.textBaseline = 'bottom';
                    const tw = g.measureText(label).width;
                    g.fillStyle = 'rgba(255,255,255,0.75)';
                    g.fillRect(x0 - 3 * dpr, baseY - 17 * dpr, Math.max(barW, tw) + 8 * dpr, 29 * dpr);
                    g.strokeStyle = '#333'; g.lineWidth = Math.max(1, 2 * dpr);
                    g.beginPath(); g.moveTo(x0, baseY - 5 * dpr); g.lineTo(x0, baseY); g.lineTo(x0 + barW, baseY); g.lineTo(x0 + barW, baseY - 5 * dpr); g.stroke();
                    g.fillStyle = '#333'; g.fillText(label, x0, baseY - 6 * dpr);
                    g.restore();
                } catch (e) { /* scale bar is best-effort */ }
            }
            // Composite the WebGL map canvas (which already contains the drawn/measured GL layers)
            // onto a 2D canvas, then paint the scale bar (an HTML control, not part of the GL canvas).
            function composite(gl) {
                const out = document.createElement('canvas'); out.width = gl.width; out.height = gl.height;
                const g = out.getContext('2d'); g.drawImage(gl, 0, 0); drawScaleBar(g, out.width, out.height); return out;
            }
            function jpegToPdf(jpeg, w, h) {
                const enc = new TextEncoder(); const parts = [], off = []; let pos = 0;
                const put = (x) => { const b = (typeof x === 'string') ? enc.encode(x) : x; parts.push(b); pos += b.length; };
                put('%PDF-1.4\\n');
                off[1] = pos; put('1 0 obj\\n<< /Type /Catalog /Pages 2 0 R >>\\nendobj\\n');
                off[2] = pos; put('2 0 obj\\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\\nendobj\\n');
                off[3] = pos; put('3 0 obj\\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' + w + ' ' + h + '] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>\\nendobj\\n');
                off[4] = pos; put('4 0 obj\\n<< /Type /XObject /Subtype /Image /Width ' + w + ' /Height ' + h + ' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ' + jpeg.length + ' >>\\nstream\\n'); put(jpeg); put('\\nendstream\\nendobj\\n');
                const content = 'q ' + w + ' 0 0 ' + h + ' 0 0 cm /Im0 Do Q';
                off[5] = pos; put('5 0 obj\\n<< /Length ' + content.length + ' >>\\nstream\\n' + content + '\\nendstream\\nendobj\\n');
                const xref = pos; let x = 'xref\\n0 6\\n0000000000 65535 f \\n'; for (let i = 1; i <= 5; i++) x += String(off[i]).padStart(10, '0') + ' 00000 n \\n'; put(x);
                put('trailer\\n<< /Size 6 /Root 1 0 R >>\\nstartxref\\n' + xref + '\\n%%EOF');
                return new Blob(parts, { type: 'application/pdf' });
            }
            jpgB.onclick = () => { ctx.freshCanvas((c) => composite(c).toBlob((b) => ctx.download(b, 'mapsplat-map-' + stamp() + '.jpg'), 'image/jpeg', 0.92)); panel.style.display = 'none'; };
            pdfB.onclick = () => { ctx.freshCanvas((c) => { const o = composite(c); const jb = b64ToBytes(o.toDataURL('image/jpeg', 0.92)); ctx.download(jpegToPdf(jb, o.width, o.height), 'mapsplat-map-' + stamp() + '.pdf'); }); panel.style.display = 'none'; };
            window.__mapsplatExport = {
                compositeDataUrl: () => composite(map.getCanvas()).toDataURL('image/jpeg', 0.92),
                jpegBytes: () => b64ToBytes(composite(map.getCanvas()).toDataURL('image/jpeg', 0.92)),
                pdfBlob: () => { const o = composite(map.getCanvas()); return jpegToPdf(b64ToBytes(o.toDataURL('image/jpeg', 0.92)), o.width, o.height); }
            };
        }});""".replace('__SCALEBAR__', _export_scalebar).replace('__ICON__', _ICON_EXPORT)) if _export_on else ""

    tools_js = (
        (_framework_js + _measure_reg + _draw_reg + _export_reg
         + "\n        MapSplatTools.install(map);")
        if _tools_any else ""
    )

    # Advanced legend toggle (Python → JS literal)
    _advanced_legend = 'true' if settings.get('advanced_legend') else 'false'

    # Popup field config: {sanitized_source_layer: [field_names]} → JSON for JS constant
    _popup_field_config_json = json.dumps(settings.get('popup_fields', {}))

    # Hatch/pattern images: {image_id: {url, pixelRatio}} → loaded on styleimagemissing
    _mapsplat_patterns_json = json.dumps(
        (style_json or {}).get("metadata", {}).get("mapsplat:patterns", {})
    )
    # Our own sprite icon names — never replace these with an empty placeholder; the sprite
    # sheet provides them (a race would otherwise blank a marker layer, e.g. point icons).
    _mapsplat_sprite_icons_json = json.dumps(
        (style_json or {}).get("metadata", {}).get("mapsplat:sprite-icons", [])
    )

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

    # MapSplat pink-blob logo as the page favicon (also stops the browser's favicon.ico 404).
    _favicon_href = "data:image/svg+xml;base64," + base64.b64encode(_logo.encode("utf-8")).decode("ascii")

    _generated_ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return f'''<!DOCTYPE html>
<!-- Generated by MapSplat v{__version__} on {_generated_ts} -->
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="{_favicon_href}">
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
            max-height: calc(100% - 20px);
            overflow-y: auto;
            overflow-x: hidden;
            box-sizing: border-box;
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
            flex-wrap: wrap;
            align-items: center;
            margin: 4px 0;
            cursor: pointer;
        }}
        /* Per-class entries wrap to their own full-width line UNDER the layer row,
           so the legend stays vertical instead of growing wide. */
        .layer-item > .legend-entries,
        .layer-item > details.legend-entries-collapse {{
            flex-basis: 100%;
            width: 100%;
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
            flex: 1;
            min-width: 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .legend-entries {{ margin: 3px 0 3px 22px; }}
        .legend-entry {{ display: flex; align-items: center; margin: 2px 0; font-size: 11px; color: #555; }}
        .legend-entry .legend-swatch {{ margin-right: 5px; flex-shrink: 0; }}
        /* Collapsible QGIS layer-tree groups */
        details.legend-group {{ margin: 2px 0; }}
        details.legend-group > summary {{
            cursor: pointer; font-size: 12px; font-weight: 600; color: #333;
            padding: 2px 0; list-style-position: inside; user-select: none;
        }}
        details.legend-group > summary:hover {{ color: #000; }}
        details.legend-group > summary .group-toggle {{ margin: 0 5px 0 0; vertical-align: middle; cursor: pointer; }}
        details.legend-group > .layer-item {{ margin-left: 14px; }}
        /* Collapsible per-layer class list ("N classes") */
        details.legend-entries-collapse {{ margin: 2px 0 2px 22px; }}
        details.legend-entries-collapse > summary {{
            cursor: pointer; font-size: 11px; color: #777; user-select: none;
        }}
        details.legend-entries-collapse > summary:hover {{ color: #333; }}
        details.legend-entries-collapse > .legend-entries {{ margin-left: 8px; }}
    </style>
    <!-- <----- END MAPSPLAT <head> section ----- -->
</head>
<body>
    <!-- <----- BEGIN MAPSPLAT: copy the lines below into your page <body> ----- -->
    <!-- NOTE: the entire MAPSPLAT <head> block above must also be present in    -->
    <!-- your target page — the MapLibre + PMTiles assets AND the <style> rules  -->
    <!-- (inline when bundled for offline use, else loaded from a CDN).          -->
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

        // Resilient layer loading: start the map with only the background layer, then add each
        // data layer individually (below). MapLibre rejects the WHOLE style if a single layer is
        // invalid (e.g. a duplicate id) — this way one bad layer is skipped, not fatal.
        const _mapsplatAllLayers = Array.isArray({style_ref}.layers) ? {style_ref}.layers.slice() : [];
        const _mapsplatDataLayers = _mapsplatAllLayers.filter(function (l) {{ return l.type !== 'background'; }});
        {style_ref}.layers = _mapsplatAllLayers.filter(function (l) {{ return l.type === 'background'; }});

        // Initialize map
        const map = new maplibregl.Map({{
            container: 'map',
            style: {style_ref},
            center: [{center_lng}, {center_lat}],
            zoom: 4,
            preserveDrawingBuffer: {_preserve_buffer}
        }});

        // Add navigation controls
        map.addControl(new maplibregl.NavigationControl(), 'top-right');{scale_bar_js}{geolocate_js}{fullscreen_js}{attribution_js}

        // Fit to data bounds on load and create layer controls
        map.on('load', () => {{
            map.fitBounds([
                [{bounds[0]}, {bounds[1]}],
                [{bounds[2]}, {bounds[3]}]
            ], {{ padding: 50 }});

            // Add each data layer on its own; skip (don't fail on) any layer MapLibre rejects,
            // so a single bad layer can't blank the whole map. Skipped layers are logged.
            const _mapsplatSkipped = [];
            for (const _lyr of _mapsplatDataLayers) {{
                try {{ map.addLayer(_lyr); }}
                catch (e) {{ _mapsplatSkipped.push(_lyr.id); console.warn('MapSplat: skipped layer "' + _lyr.id + '" — ' + (e && e.message)); }}
            }}
            if (_mapsplatSkipped.length) console.warn('MapSplat: ' + _mapsplatSkipped.length + ' layer(s) could not be added; the rest of the map still works.');

            // Create layer toggles
            const layerToggles = document.getElementById('layer-toggles');
            const style = map.getStyle();
            // Reverse so top layers appear first in the list (MapLibre renders bottom-to-top).
            // Include raster layers (imagery, XYZ basemap, online raster) — they have no
            // 'source-layer' but still need a TOC entry so users can toggle them off.
            const layers = style.layers.filter(l => l['source-layer'] || l.type === 'raster').reverse();
            // Group key: source-aware so identically-named source-layers from different sources
            // (e.g. a Carto vector tile's 'water' vs the basemap's 'water') stay separate.
            const _groupKey = (l) => (l.source || '') + '\x1f' + (l['source-layer'] || l.id);

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
                if (raw) return extractColorFromExpression(raw) || '#888888';
                // Symbol layers have no paint color — fall back to embedded SVG fill color
                const meta = layer.metadata;
                if (meta && meta['mapsplat:fill-color']) return meta['mapsplat:fill-color'];
                return '#888888';
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
                }} else if (ltype === 'raster') {{
                    // Raster / imagery / basemap: a small gradient tile icon.
                    swatch.style.cssText = 'background:linear-gradient(135deg,#7fa8c9,#cfe3d4);'
                        + 'border:1px solid #999;width:16px;height:16px;min-width:16px;';
                }} else if (ltype === 'symbol') {{
                    // Use the pre-rendered icon data URL embedded in layer metadata (single-symbol
                    // marker) or the first per-class icon (categorized markers).
                    const meta = layer.metadata || {{}};
                    const _cls = meta['mapsplat:legend-classes'];
                    const iconDataUrl = meta['mapsplat:legend-icon']
                        || (_cls && _cls.length && _cls[0].icon);
                    if (iconDataUrl) {{
                        swatch.style.cssText = 'background-image:url(' + iconDataUrl + ');'
                            + 'background-size:contain;background-repeat:no-repeat;'
                            + 'background-position:center;background-color:transparent;border:none;'
                            + 'width:16px;height:16px;min-width:16px;';
                    }} else {{
                        swatch.classList.add('circle');
                        swatch.style.backgroundColor = color;
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

            // A legend row showing a sprite-icon (data URL) + label — for marker classes.
            function makeIconEntry(iconUrl, label) {{
                const row = document.createElement('div');
                row.className = 'legend-entry';
                const s = document.createElement('div');
                s.className = 'legend-swatch';
                s.style.cssText = 'background-image:url(' + iconUrl + ');background-size:contain;'
                    + 'background-repeat:no-repeat;background-position:center;background-color:transparent;'
                    + 'border:none;width:16px;height:16px;min-width:16px;';
                row.appendChild(s);
                const lbl = document.createElement('span');
                lbl.textContent = String(label);
                row.appendChild(lbl);
                return row;
            }}

            // Build per-class/category legend entries from a layer's paint expression
            function buildLegendEntries(layer) {{
                // Categorized markers: per-class sprite icons embedded in layer metadata.
                const _cls = (layer.metadata || {{}})['mapsplat:legend-classes'];
                if (_cls && _cls.length) {{
                    return _cls.filter(c => c && c.icon).map(c => makeIconEntry(c.icon, c.label));
                }}
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
            //   fill(0) > line(1) > circle(2) > icon-symbol(2.5) > label-only-symbol(3)
            function _layerPri(l) {{
                if (l.type === 'fill')   return 0;
                if (l.type === 'line')   return 1;
                if (l.type === 'circle') return 2;
                if (l.type === 'symbol') {{
                    // Icon symbol layers beat label-only symbol layers
                    return (l.layout && l.layout['icon-image']) ? 2.5 : 3;
                }}
                return 99;
            }}
            const _slOrder = [], _slGroups = {{}};
            layers.forEach(layer => {{
                const sl = _groupKey(layer);
                if (!_slGroups[sl]) {{ _slGroups[sl] = []; _slOrder.push(sl); }}
                _slGroups[sl].push(layer);
            }});

            // Build one legend row (checkbox + swatch + label, plus per-class entries).
            let _tocSeq = 0;
            function renderLayerItem(sourceLayer) {{
                const groupLayers = _slGroups[sourceLayer];
                if (!groupLayers) return null;
                const layer = groupLayers.reduce((best, l) =>
                    _layerPri(l) < _layerPri(best) ? l : best);

                const div = document.createElement('div');
                div.className = 'layer-item';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = 'toggle-' + (_tocSeq++);
                checkbox.checked = true;

                const label = document.createElement('label');
                label.htmlFor = checkbox.id;
                // Display the source-layer/id part of the composite key (drop the source prefix).
                const _slName = sourceLayer.split('\x1f').pop();
                const _lblMeta = (layer.metadata || {{}})['mapsplat:label'];
                label.textContent = _lblMeta || _slName
                    .replace(/^(tile_|raster_)/, '').replace(/(_raster|_layer)$/, '').replace(/_/g, ' ');
                label.title = _slName;

                checkbox.addEventListener('change', () => {{
                    groupLayers.forEach(l => map.setLayoutProperty(l.id, 'visibility',
                        checkbox.checked ? 'visible' : 'none'));
                }});

                div.appendChild(checkbox);
                div.appendChild(makeLayerSwatch(layer));
                div.appendChild(label);

                // Per-class marker icons define the layer, so always show them; the
                // advanced-legend toggle only gates the colour-inferred class breakdowns.
                const _hasIconClasses =
                    (((layer.metadata || {{}})['mapsplat:legend-classes']) || []).length > 0;
                if ({_advanced_legend} || _hasIconClasses) {{
                    const entries = buildLegendEntries(layer);
                    if (entries.length > 1) {{
                        // Collapse long class lists behind an "N classes" toggle.
                        if (entries.length > 6) {{
                            const det = document.createElement('details');
                            det.className = 'legend-entries-collapse';
                            const sum = document.createElement('summary');
                            sum.textContent = entries.length + ' classes';
                            det.appendChild(sum);
                            const ed = document.createElement('div');
                            ed.className = 'legend-entries';
                            entries.forEach(e => ed.appendChild(e));
                            det.appendChild(ed);
                            div.appendChild(det);
                        }} else {{
                            const ed = document.createElement('div');
                            ed.className = 'legend-entries';
                            entries.forEach(e => ed.appendChild(e));
                            div.appendChild(ed);
                        }}
                    }}
                }}
                return div;
            }}

            // A collapsible group whose summary has a checkbox that shows/hides EVERY layer in it.
            function makeGroupSection(name) {{
                const det = document.createElement('details');
                det.className = 'legend-group';
                const sum = document.createElement('summary');
                const gcb = document.createElement('input');
                gcb.type = 'checkbox'; gcb.checked = true; gcb.className = 'group-toggle';
                gcb.title = 'Show/hide all layers in this group';
                gcb.addEventListener('click', (e) => e.stopPropagation());  // don't toggle the disclosure
                gcb.addEventListener('change', () => {{
                    det.querySelectorAll('.layer-item > input[type="checkbox"]').forEach(cb => {{
                        if (cb.checked !== gcb.checked) {{ cb.checked = gcb.checked; cb.dispatchEvent(new Event('change')); }}
                    }});
                }});
                sum.appendChild(gcb);
                const lbl = document.createElement('span');
                lbl.textContent = name;
                sum.appendChild(lbl);
                det.appendChild(sum);
                // Keep the group checkbox in sync with its children (all / none / mixed).
                det.addEventListener('change', (e) => {{
                    if (e.target === gcb) return;
                    const boxes = [...det.querySelectorAll('.layer-item > input[type="checkbox"]')];
                    const on = boxes.filter(b => b.checked).length;
                    gcb.checked = on > 0;
                    gcb.indeterminate = on > 0 && on < boxes.length;
                }});
                return det;
            }}

            // QGIS layer-tree groups → collapsible sections (collapsed by default). The metadata
            // lists a group's members by source-layer NAME; match those to the source-aware group
            // keys (and only to real data layers, never a base/basemap layer of the same name).
            const legendGroups = (style.metadata || {{}})['mapsplat:legend-groups'] || [];
            const grouped = new Set();
            const _isBaseSrc = (s) => (s || '').startsWith('tile_') || (s || '').startsWith('raster_')
                || s === 'protomaps' || s === 'basemap_xyz';
            legendGroups.forEach(g => {{
                if (!g.name) return;
                const det = makeGroupSection(g.name);
                (g.layers || []).forEach(sl => {{
                    _slOrder.forEach(key => {{
                        if (grouped.has(key)) return;
                        const gl = _slGroups[key];
                        if (gl && gl[0] && !_isBaseSrc(gl[0].source) && key.split('\x1f').pop() === sl) {{
                            const item = renderLayerItem(key);
                            if (item) {{ det.appendChild(item); grouped.add(key); }}
                        }}
                    }});
                }});
                if (det.children.length > 1) layerToggles.appendChild(det);
            }});

            // Base layers — styled vector tiles (e.g. Carto) and the basemap — go into their own
            // collapsible sections at the BOTTOM of the list (below your data), matching the map's
            // base-at-bottom order. Claim their layers now so the ungrouped pass skips them.
            const _bottomSections = [];
            function _makeSourceGroup(name, sourceMatch) {{
                const det = makeGroupSection(name);
                _slOrder.forEach(key => {{
                    if (grouped.has(key)) return;
                    const gl = _slGroups[key];
                    if (gl && gl[0] && sourceMatch(gl[0].source)) {{
                        const item = renderLayerItem(key);
                        if (item) {{ det.appendChild(item); grouped.add(key); }}
                    }}
                }});
                if (det.children.length > 1) _bottomSections.push(det);
            }}

            ((style.metadata || {{}})['mapsplat:tile-groups'] || []).forEach(tg => {{
                if (tg.name && tg.source) _makeSourceGroup(tg.name, (s) => s === tg.source);
            }});
            const _bmGroup = (style.metadata || {{}})['mapsplat:basemap-group'];
            if (_bmGroup && Array.isArray(_bmGroup.sources) && _bmGroup.sources.length) {{
                const _bmSet = new Set(_bmGroup.sources);
                _makeSourceGroup(_bmGroup.name || 'Basemap', (s) => _bmSet.has(s));
            }}

            // Your data layers (ungrouped) in the middle, in render order.
            _slOrder.forEach(sourceLayer => {{
                if (grouped.has(sourceLayer)) return;
                const item = renderLayerItem(sourceLayer);
                if (item) layerToggles.appendChild(item);
            }});

            // Base sections at the very bottom.
            _bottomSections.forEach(det => layerToggles.appendChild(det));
        }});

        // When the basemap sprite is replaced by the local business sprite, all
        // basemap icon-image keys (shields, POIs, etc.) become missing.  In
        // MapLibre 4.x, unhandled styleimagemissing events stall the symbol
        // rendering queue and prevent business-layer icons from appearing.
        // Adding a transparent 1×1 placeholder immediately unblocks rendering.
        // Hatch/pattern images generated at export time (QGIS hatch fills).
        const mapsplatPatterns = {_mapsplat_patterns_json};
        // Our own sprite icons: never substitute a placeholder — the sprite provides them.
        const mapsplatSpriteIcons = new Set({_mapsplat_sprite_icons_json});
        map.on('styleimagemissing', (e) => {{
            if (map.hasImage(e.id)) return;
            // A sprite icon may fire this before the sprite finishes loading; leave it for
            // the sprite (adding an empty image here would permanently blank the marker).
            if (mapsplatSpriteIcons.has(e.id)) return;
            const pat = mapsplatPatterns[e.id];
            if (pat && pat.url) {{
                // Load the real hatch tile; fall back to a transparent pixel on error.
                map.loadImage(pat.url).then((res) => {{
                    if (!map.hasImage(e.id)) {{
                        map.addImage(e.id, res.data, {{pixelRatio: pat.pixelRatio || 1}});
                    }}
                }}).catch(() => {{
                    if (!map.hasImage(e.id)) {{
                        map.addImage(e.id, new ImageData(new Uint8ClampedArray(4), 1, 1));
                    }}
                }});
                return;
            }}
            // Unknown missing image (e.g. basemap sprite icon): transparent placeholder
            // so the symbol render queue doesn't stall.
            const empty = new ImageData(new Uint8ClampedArray(4), 1, 1);
            map.addImage(e.id, empty);
        }});

        // Dual-sprite fallback. When basemap + business sprites are combined into a MapLibre
        // sprite ARRAY, a single unreachable URL (e.g. the remote basemap sprite offline) makes
        // the whole array fail to load — which would blank our local business markers too. On a
        // sprite load error, drop the failing entries and keep the local 'mapsplat' sprite so our
        // markers still render (basemap shield/POI icons are sacrificed, but they were missing
        // anyway). Runs at most once.
        let _mapsplatSpriteFallback = false;
        map.on('error', (e) => {{
            if (_mapsplatSpriteFallback) return;
            const err = e && e.error;
            const url = (err && (err.url || (err.request && err.request.url))) || '';
            const msg = (err && err.message) || '';
            if (!/sprite/i.test(url) && !/sprite/i.test(msg)) return;
            const st = map.getStyle();
            const sprite = st && st.sprite;
            if (!Array.isArray(sprite)) return;
            const mine = sprite.filter((s) => s && s.id === 'mapsplat');
            if (!mine.length || mine.length === sprite.length) return;
            _mapsplatSpriteFallback = true;
            console.warn('MapSplat: a sprite failed to load; falling back to the local business sprite so markers still render.');
            try {{
                if (typeof map.setSprite === 'function') {{
                    map.setSprite(mine);
                }} else {{
                    st.sprite = mine;
                    map.setStyle(st, {{ diff: false }});
                }}
            }} catch (err2) {{ console.error('MapSplat sprite fallback failed', err2); }}
        }});

        // Popup field visibility config: source-layer name → allowed field names (null = all)
        const popupFieldConfig = {_popup_field_config_json};

        // Click handler for feature identification
        map.on('click', (e) => {{
            // Suppress identify popups while an interactive tool (measure/draw) is capturing clicks.
            if (window.__mapsplatToolActive) return;
            const features = map.queryRenderedFeatures(e.point);
            if (features.length > 0) {{
                const feature = features[0];
                const props = feature.properties;
                const _allowed = popupFieldConfig[feature.sourceLayer];
                const _entries = _allowed
                    ? Object.entries(props).filter(([k]) => _allowed.includes(k))
                    : Object.entries(props);

                let html = '<div style="max-width:300px;max-height:200px;overflow:auto;">';
                for (const [key, value] of _entries) {{
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
        }});{coords_js}{zoom_js}{reset_view_js}{north_reset_js}{tools_js}{_init_close}
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
        if self._qprocess and self._qprocess.state() != QProcess.ProcessState.NotRunning:
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
        # Per-layer outcome tracking for the end-of-run summary (Story 3) and PMTiles
        # verification (Story 14). _failed_layers holds (layer_name, reason) tuples.
        self._failed_layers = []
        self._export_summary = None
        self._tile_groups = []  # {name, source} per styled vector-tile layer, for the TOC
        self._basemap_sources = []  # basemap source id(s), grouped under a "Basemap" TOC section
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

        # Compute export bounds once; reuse for basemap extraction and data clip
        base_bounds = self._get_bounds(layers)
        clip_rect = self._bounds_to_rect_3857(self._expand_bounds(base_bounds, pct=0.5))

        # [NEW] Basemap: "bundle" clips+embeds offline (needs the pmtiles CLI);
        # "stream" points the viewer at the remote URL (no CLI, no extraction).
        basemap_mode = self.settings.get("basemap_mode", "bundle")
        if use_basemap and not style_only and basemap_mode == "bundle":
            if not self._check_pmtiles_cli():
                self.log_message.emit(
                    "pmtiles CLI not found. Install it from https://github.com/protomaps/go-pmtiles/releases"
                    " — or switch the basemap to 'Stream from URL' mode (no install needed).",
                    "error"
                )
                self.finished.emit(False, "")
                return
            basemap_bounds = self._expand_bounds(base_bounds)  # 0.5% buffer for tile alignment
            self.log_message.emit("Extracting basemap to bounding box...", "info")
            success = self._extract_basemap(output_dir, basemap_bounds)
            if not success:
                self.finished.emit(False, "")
                return
            self._maybe_verify(os.path.join(output_dir, "data", "basemap.pmtiles"), "basemap")
        elif use_basemap and not style_only and basemap_mode == "xyz":
            self.log_message.emit("Basemap: XYZ raster tiles (streams live; no extraction).", "info")
            self.progress.emit(30)
        elif use_basemap and not style_only:
            self.log_message.emit("Basemap: streaming live from the remote URL (no extraction).", "info")
            self.progress.emit(30)

        # Layers that actually made it into tiles — only these get style layers/sources,
        # so a layer that fails to tile can't leave a dangling "source not found" reference.
        exported_vector = list(layers["vector"])

        if style_only:
            # Skip data export, just generate style and HTML
            self.log_message.emit("Style-only mode: skipping data export", "info")
            self.progress.emit(60)
        elif single_file:
            # Single PMTiles file containing all layers
            self.log_message.emit("Exporting layers to GeoPackage...", "info")
            gpkg_path = os.path.join(output_dir, "data", "layers.gpkg")
            self._export_to_geopackage(layers["vector"], gpkg_path, clip_rect)
            self.progress.emit(40)

            self.log_message.emit("Converting to PMTiles...", "info")
            pmtiles_path = os.path.join(output_dir, "data", "layers.pmtiles")
            success = self._convert_to_pmtiles(gpkg_path, pmtiles_path)
            if not success:
                self.finished.emit(False, "")
                return
            self._maybe_verify(pmtiles_path, "layers.pmtiles")
            self.progress.emit(60)

            # Clean up intermediate GeoPackage
            if os.path.exists(gpkg_path):
                os.remove(gpkg_path)
        else:
            # Separate PMTiles file per layer
            self.log_message.emit("Exporting layers separately...", "info")
            total_layers = len(layers["vector"])
            exported_vector = []
            for i, layer in enumerate(layers["vector"]):
                if self._cancelled:
                    self.log_message.emit("Export cancelled.", "warning")
                    self.finished.emit(False, "")
                    return

                layer_name = self._sanitize_layer_name(layer.name())
                self.log_message.emit(f"Processing layer {i + 1}/{total_layers}: {layer.name()}", "info")

                # Export single layer to GeoPackage (clipped to export extent)
                gpkg_path = os.path.join(output_dir, "data", f"{layer_name}.gpkg")
                self._export_to_geopackage([layer], gpkg_path, clip_rect)

                # Convert to PMTiles
                pmtiles_path = os.path.join(output_dir, "data", f"{layer_name}.pmtiles")
                success = self._convert_to_pmtiles(gpkg_path, pmtiles_path)
                if not success:
                    self.log_message.emit(f"Failed to convert {layer_name}", "error")
                    # Continue with other layers instead of aborting. Do NOT add it to
                    # exported_vector, so no dangling style layer/source is emitted for it.
                    self._failed_layers.append((layer.name(), "PMTiles conversion failed"))
                    continue

                # Optional integrity check (Story 14). A verify failure records the layer
                # but keeps it in the map — the tiles were written, just flagged as suspect.
                self._maybe_verify(pmtiles_path, layer.name())

                exported_vector.append(layer)

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
            exported_vector,
            self.settings,
            log_callback=lambda msg: self.log_message.emit(msg, "info"),
        )
        style_json = style_converter.convert(
            single_file=single_file,
            output_dir=output_dir if not style_only else None,
        )

        # Reference any selected tile-service layers (MVT vector tiles / XYZ-WMS rasters) as
        # pass-through sources in the style. No data is copied — the viewer streams them live.
        self._add_tile_layers(layers.get("tile", []), style_json, output_dir, style_only)

        # Tile selected local raster layers to PMTiles (opt-in), below the vector layers.
        if not style_only:
            self._export_raster_layers(layers.get("raster", []), output_dir, style_json, base_bounds)

        # Order all business layers (vector + tile + raster) to match the QGIS layer tree, so a
        # tile/raster layer appears where it does in QGIS instead of always at the bottom.
        self._reorder_business_by_tree(style_json)

        # Handle style merging
        if use_basemap and basemap_mode == "xyz":
            self._add_xyz_basemap(
                style_json,
                self.settings.get("basemap_source", "").strip(),
                self.settings.get("basemap_attribution", ""),
            )
        elif use_basemap:
            basemap_style_path = self.settings.get("basemap_style_path", "")
            self.log_message.emit("Merging business layers into basemap style...", "info")
            style_json = self._merge_business_into_basemap(basemap_style_path, style_json)
        elif self.settings.get("imported_style_path"):
            style_json = self._merge_imported_style(style_json)

        # Safety net: drop any layer whose source is missing, so a single dangling
        # reference can't make MapLibre reject the entire style ("source not found").
        style_json = self._prune_orphan_layers(style_json)
        # Safety net: a duplicate layer id makes MapLibre reject the ENTIRE style. Rename any
        # collisions so one clashing layer can't blank the whole map.
        self._dedupe_layer_ids(style_json)

        # Stamp the build so serve.py and the viewer can report which export this is.
        _meta = style_json.setdefault("metadata", {})
        _meta["mapsplat:version"] = self._plugin_version()
        _meta["mapsplat:project"] = self.settings.get("project_name", "")
        # Styled vector-tile layers (e.g. Carto) → their own collapsible TOC section in the viewer.
        if self._tile_groups:
            _meta["mapsplat:tile-groups"] = self._tile_groups
        # Basemap layers → a collapsible "Basemap" section (keeps the many basemap sub-layers tidy).
        if self._basemap_sources:
            _meta["mapsplat:basemap-group"] = {"name": "Basemap", "sources": self._basemap_sources}

        # Report the final style so the Log tab shows exactly what was written.
        _biz = sorted({ly["source"] for ly in style_json.get("layers", [])
                       if ly.get("source") and ly["source"] != "protomaps"})
        self.log_message.emit(
            f"Final style: {len(style_json.get('layers', []))} layers, "
            f"{len(style_json.get('sources', {}))} sources; data layers: "
            + (", ".join(_biz) if _biz else "(none)"), "info"
        )

        # Flag sources that stream live from a remote server — the map is NOT fully self-hosted
        # for these (they need internet and aren't served by your own static host / Caddy).
        _streaming = []
        for _sid, _src in style_json.get("sources", {}).items():
            _urls = _src.get("tiles") or ([_src["url"]] if _src.get("url") else [])
            if any(isinstance(u, str) and u.startswith(("http://", "https://")) for u in _urls):
                _streaming.append(_sid)
        if _streaming:
            self.log_message.emit(
                f"Note: {len(_streaming)} source(s) stream live and need internet — the exported map "
                f"is NOT fully self-hosted for these (your own Caddy/static host won't serve them): "
                + ", ".join(sorted(_streaming)), "warning"
            )

        self.progress.emit(75)

        # Write style.json if requested
        if self.settings["export_style_json"]:
            style_path = os.path.join(output_dir, "style.json")
            with open(style_path, "w", encoding="utf-8") as f:
                json.dump(style_json, f, indent=2)
            self.log_message.emit("Wrote style.json", "info")

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

        # Export summary (Story 3) — total selected vs. those with issues. Exposed on the
        # instance so the dock can show a summary dialog on partial failure.
        total_selected = (len(layers.get("vector", [])) + len(layers.get("raster", []))
                          + len(layers.get("tile", [])))
        failed_names = {name for name, _ in self._failed_layers}
        succeeded = max(0, total_selected - len(failed_names))
        self._export_summary = {
            "total": total_selected,
            "succeeded": succeeded,
            "failed": list(self._failed_layers),
        }
        if self._failed_layers:
            self.log_message.emit(
                f"Export finished with issues: {succeeded} of {total_selected} layer(s) OK; "
                f"{len(failed_names)} had problems.", "warning"
            )
            for name, reason in self._failed_layers:
                self.log_message.emit(f"  ✗ {name}: {reason}", "warning")
        else:
            self.log_message.emit(f"All {total_selected} selected layer(s) exported.", "success")

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
        layers = {"vector": [], "raster": [], "tile": []}

        for layer_id in self.settings["layer_ids"]:
            layer = self.project.mapLayer(layer_id)
            if layer is None:
                continue

            if QgsVectorTileLayer is not None and isinstance(layer, QgsVectorTileLayer):
                # MVT/PBF vector tile service → referenced (pass-through) in style.json
                layers["tile"].append(layer)
            elif isinstance(layer, QgsVectorLayer):
                layers["vector"].append(layer)
            elif isinstance(layer, QgsRasterLayer):
                # XYZ / WMS / WMTS rasters use the 'wms' provider in QGIS — reference them as
                # online raster tile sources. Local GDAL rasters go to the raster export path.
                prov = layer.dataProvider().name() if layer.dataProvider() else ""
                if prov == "wms":
                    layers["tile"].append(layer)
                else:
                    layers["raster"].append(layer)

        return layers

    def _export_to_geopackage(self, layers, gpkg_path, clip_rect=None):
        """Export vector layers to a GeoPackage.

        :param layers: List of QgsVectorLayer
        :param gpkg_path: Output GeoPackage path
        :param clip_rect: Optional QgsRectangle in EPSG:3857 to spatially clip features
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

            # Transform to Web Mercator. Reproject from ANY valid source CRS; a layer
            # with an invalid/unset CRS can't be placed on a web map, so warn and skip
            # it (rather than emit points at null island or a dangling source).
            src_crs = layer.crs()
            if not src_crs.isValid():
                self.log_message.emit(
                    f"  Skipping '{layer.name()}': layer has no valid CRS — set one in QGIS "
                    f"(Layer Properties ▸ Source) and re-export.", "warning"
                )
                continue
            if src_crs != self.target_crs:
                options.ct = QgsCoordinateTransform(
                    src_crs,
                    self.target_crs,
                    self.project
                )

            # Clip to export extent (filterExtent is in destination CRS = EPSG:3857)
            if clip_rect is not None:
                options.filterExtent = clip_rect

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

        # The GeoPackage is always written in EPSG:3857 by _export_to_geopackage
        # (QgsVectorFileWriter applies options.ct to reproject every layer).
        # Specifying -s_srs EPSG:3857 prevents ogr2ogr from attempting a second
        # reprojection when the CRS WKT stored by QGIS is not recognised by GDAL
        # as exactly EPSG:3857 — which would cause visible geometry distortion.
        args = [
            "-f", "PMTiles",
            "-dsco", "MINZOOM=0",
            "-dsco", f"MAXZOOM={max_zoom}",
            "-s_srs", "EPSG:3857",
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
        while self._qprocess.state() != QProcess.ProcessState.NotRunning:
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

    def _run_cmd(self, args, timeout=1800):
        """Run a blocking external command. Returns (ok: bool, error: str)."""
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
                startupinfo=STARTUPINFO, creationflags=CREATIONFLAGS,
            )
        except FileNotFoundError:
            return False, f"{args[0]} not found"
        except subprocess.TimeoutExpired:
            return False, "timed out"
        except Exception as e:  # pragma: no cover - defensive
            return False, str(e)
        if r.returncode != 0:
            return False, (r.stderr.strip() or r.stdout.strip() or f"exit code {r.returncode}")
        return True, ""

    def _check_gdal_mbtiles(self):
        """True if GDAL's MBTiles raster driver is available (needed to tile rasters)."""
        try:
            r = subprocess.run(
                ["gdal_translate", "--formats"], capture_output=True, text=True, timeout=15,
                startupinfo=STARTUPINFO, creationflags=CREATIONFLAGS,
            )
            return "MBTiles" in r.stdout
        except Exception:
            return False

    def _raster_to_pmtiles(self, layer, output_dir, name, bounds):
        """Tile one raster layer to PMTiles: gdalwarp→3857 → MBTiles → overviews → pmtiles convert.

        Handles RGB(A) imagery directly and paletted rasters via an ``-expand rgba`` retry.
        Single-band continuous rasters (e.g. styled DEMs) may fail here — they'd need QGIS
        rendering, which is a later stage. Returns True on success.
        """
        import tempfile
        import shutil

        src = layer.source() or ""
        src_path = src.split("|")[0]  # strip GDAL "|option=..." suffixes
        if not os.path.exists(src_path):
            self.log_message.emit(f"  Raster source not found: {src_path}", "error")
            return False

        west, south, east, north = bounds
        tmp = tempfile.mkdtemp(prefix="mapsplat_raster_")
        warped = os.path.join(tmp, f"{name}_3857.tif")
        mbtiles = os.path.join(tmp, f"{name}.mbtiles")
        pmtiles_out = os.path.join(output_dir, "data", f"{name}.pmtiles")
        try:
            # 1) Reproject to Web Mercator, clipped to the export extent (bounds are EPSG:4326).
            ok, err = self._run_cmd([
                "gdalwarp", "-overwrite", "-t_srs", "EPSG:3857", "-r", "bilinear",
                "-te", str(west), str(south), str(east), str(north), "-te_srs", "EPSG:4326",
                src_path, warped,
            ])
            if not ok:
                self.log_message.emit(f"  gdalwarp failed: {err}", "error")
                return False

            # 2) Tile into an MBTiles pyramid. Retry paletted rasters via -expand rgba.
            ok, err = self._run_cmd(
                ["gdal_translate", "-of", "MBTiles", "-co", "TILE_FORMAT=PNG", warped, mbtiles])
            if not ok:
                rgba = os.path.join(tmp, f"{name}_rgba.tif")
                exp_ok, _ = self._run_cmd(["gdal_translate", "-expand", "rgba", warped, rgba])
                if exp_ok:
                    ok, err = self._run_cmd(
                        ["gdal_translate", "-of", "MBTiles", "-co", "TILE_FORMAT=PNG", rgba, mbtiles])
            if not ok:
                self.log_message.emit(f"  Raster tiling failed (gdal_translate MBTiles): {err}", "error")
                return False

            # 3) Build overviews so lower zoom levels aren't blank.
            self._run_cmd(["gdaladdo", "-r", "average", mbtiles, "2", "4", "8", "16", "32"])

            # 4) MBTiles → PMTiles.
            ok, err = self._run_cmd(["pmtiles", "convert", mbtiles, pmtiles_out])
            if not ok:
                self.log_message.emit(f"  pmtiles convert failed: {err}", "error")
                return False

            if os.path.exists(pmtiles_out):
                size_mb = os.path.getsize(pmtiles_out) / (1024 * 1024)
                self.log_message.emit(f"  Tiled raster '{layer.name()}' ({size_mb:.1f} MB)", "success")
            return True
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _export_raster_layers(self, raster_layers, output_dir, style_json, bounds):
        """Tile selected local raster layers to PMTiles and add raster sources to the style.

        Gated behind the 'Include raster layers' option (off by default — tiling is slow and needs
        GDAL's MBTiles driver). Raster layers are placed below the vector layers.
        """
        if not raster_layers:
            return
        if not self.settings.get("include_rasters"):
            self.log_message.emit(
                f"  {len(raster_layers)} raster layer(s) selected but 'Include raster layers' is off "
                f"— skipped.", "warning")
            for layer in raster_layers:
                self._failed_layers.append((layer.name(), "raster export disabled ('Include raster layers' off)"))
            return
        if not self._check_gdal_mbtiles():
            self.log_message.emit(
                "  GDAL MBTiles driver not available — cannot tile rasters. Install/upgrade GDAL: "
                "https://gdal.org", "error")
            for layer in raster_layers:
                self._failed_layers.append((layer.name(), "GDAL MBTiles driver missing"))
            return

        sources = style_json.setdefault("sources", {})
        below = []
        for layer in raster_layers:
            name = self._sanitize_layer_name(layer.name())
            self.log_message.emit(f"  Tiling raster '{layer.name()}' (this can take a while)...", "info")
            if self._raster_to_pmtiles(layer, output_dir, name, bounds):
                src_id = f"raster_{name}"
                sources[src_id] = {"type": "raster", "url": f"pmtiles://data/{name}.pmtiles",
                                   "tileSize": 256}
                below.append({
                    "id": f"raster_{name}_layer",
                    "type": "raster",
                    "source": src_id,
                    "paint": {"raster-opacity": round(float(layer.opacity()), 3)},
                    "metadata": {"mapsplat:label": layer.name()},
                })
            else:
                self._failed_layers.append((layer.name(), "raster tiling failed"))
        if below:
            arr = style_json.setdefault("layers", [])
            insert_at = 1 if (arr and arr[0].get("type") == "background") else 0
            arr[insert_at:insert_at] = below

    def _add_xyz_basemap(self, style_json, url, attribution):
        """Add an online XYZ raster basemap as the bottom layer of the style (Story 16).

        Streams live in the viewer — no data is downloaded. Attribution rides on the source so
        MapLibre's attribution control shows it (most providers require attribution).
        """
        if not url:
            self.log_message.emit("  XYZ basemap URL is empty; skipping basemap", "warning")
            return
        src = {"type": "raster", "tiles": [url], "tileSize": 256}
        if attribution:
            src["attribution"] = attribution
        style_json.setdefault("sources", {})["basemap_xyz"] = src
        arr = style_json.setdefault("layers", [])
        insert_at = 1 if (arr and arr[0].get("type") == "background") else 0
        arr[insert_at:insert_at] = [
            {"id": "basemap_xyz_layer", "type": "raster", "source": "basemap_xyz",
             "metadata": {"mapsplat:label": "Basemap"}}
        ]
        self._basemap_sources = ["basemap_xyz"]
        self.log_message.emit(f"  XYZ raster basemap: {url}", "info")

    def _reorder_business_by_tree(self, style_json):
        """Place tile/raster (basemap-like) layers BELOW the vector data layers.

        Imagery and tile services are bases — they should sit under the vector overlays, not on top
        of them. The style converter already orders the vector layers correctly; tile/raster layers
        were appended at various positions, which left an opaque XYZ raster or a full vector-tile
        basemap (Carto) rendering over the data. This moves every tile/raster layer to the bottom of
        the (pre-merge) business stack — above the background/basemap, below the vectors — while
        preserving each partition's internal order (a stable partition, not a sort).
        """
        layers = style_json.get("layers", [])
        if not layers:
            return

        def _is_base(ly):
            src = ly.get("source") or ""
            return (ly.get("type") == "raster" or src.startswith(("tile_", "raster_"))
                    or src == "basemap_xyz")

        bg = [ly for ly in layers if ly.get("type") == "background"]
        rest = [ly for ly in layers if ly.get("type") != "background"]
        base = [ly for ly in rest if _is_base(ly)]     # imagery / tile bases → bottom
        vectors = [ly for ly in rest if not _is_base(ly)]  # vector data → on top
        style_json["layers"] = bg + base + vectors

    def _xyz_url_from_raster(self, layer):
        """Extract the ``{z}/{x}/{y}`` URL template from an XYZ/WMS raster layer source.

        QGIS stores XYZ rasters as ``type=xyz&url=<percent-encoded template>&...``.
        Returns the decoded template, or None if it isn't a usable XYZ template.
        """
        import re
        import urllib.parse
        src = layer.source() or ""
        m = re.search(r'(?:^|&)url=([^&]+)', src)
        if not m:
            return None
        url = urllib.parse.unquote(m.group(1))
        if "{z}" in url and "{x}" in url and "{y}" in url:
            return url
        return None

    def _style_url_from_vt(self, layer):
        """A vector-tile layer's Mapbox-GL style URL, if it was added with one (``styleUrl=``)."""
        import re
        import urllib.parse
        src = ""
        try:
            src = layer.dataProvider().dataSourceUri()
        except Exception:
            pass
        src = src or (layer.source() or "")
        m = re.search(r'(?:^|&)styleUrl=([^&]+)', src)
        if m:
            return urllib.parse.unquote(m.group(1))
        return None

    def _fetch_gl_style(self, url):
        """Fetch a Mapbox-GL style JSON from a URL at export time (best-effort)."""
        if not (isinstance(url, str) and url.startswith(("http://", "https://"))):
            return None
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "MapSplat"})
            with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310 - user layer's own style URL
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.log_message.emit(f"  Could not fetch style from {url}: {e}", "warning")
            return None

    def _gl_layers_for_source(self, gl_style, src_id):
        """Return the non-background layers from a stored GL style, re-pointed at ``src_id``."""
        if not gl_style:
            return []
        try:
            style = json.loads(gl_style) if isinstance(gl_style, str) else gl_style
        except (ValueError, TypeError):
            return []
        out = []
        for lay in style.get("layers", []):
            if lay.get("type") == "background":
                continue
            lay = dict(lay)
            if lay.get("source"):
                lay["source"] = src_id
            # Namespace the id so a provider style's generic ids (water, landcover, ...) don't
            # collide with the basemap's — a duplicate layer id makes MapLibre reject the whole style.
            lay["id"] = f"{src_id}__{lay.get('id', 'layer')}"
            out.append(lay)
        return out

    def _mbtiles_gl_style(self, mbtiles_path):
        """Read a stored Mapbox-GL style from an MBTiles ``metadata`` table, or None."""
        import sqlite3
        try:
            con = sqlite3.connect(mbtiles_path)
            try:
                rows = con.execute(
                    "SELECT name, value FROM metadata WHERE name IN ('style','json')").fetchall()
            finally:
                con.close()
        except Exception:
            return None
        meta = {n: v for n, v in rows}
        for key in ("style", "json"):
            v = meta.get(key)
            if v and '"layers"' in v:
                return v
        return None

    def _add_tile_layers(self, tile_layers, style_json, output_dir=None, style_only=False):
        """MVT vector-tile and XYZ/WMS raster layers in the style.

        - XYZ/WMS sources are **pass-through** (referenced live; no data copied, no ToS concern).
        - Local **MBTiles** vector-tile layers are converted to PMTiles and **bundled** for offline
          use (Story 18 Stage 2 — local file, no ToS concern), with the GL style from the layer's
          custom property or the MBTiles metadata table.

        Tile layers are inserted *below* the exported vector PMTiles layers.
        """
        if not tile_layers:
            return
        sources = style_json.setdefault("sources", {})
        below = []  # inserted at the bottom of the layer stack
        for layer in tile_layers:
            name = self._sanitize_layer_name(layer.name())
            src_id = f"tile_{name}"
            if QgsVectorTileLayer is not None and isinstance(layer, QgsVectorTileLayer):
                stype = layer.sourceType() if hasattr(layer, "sourceType") else ""
                url = layer.sourcePath() if hasattr(layer, "sourcePath") else ""

                if stype == "mbtiles":
                    # Stage 2: convert the local MBTiles to PMTiles and bundle it.
                    if style_only or not output_dir:
                        self.log_message.emit(
                            f"  Skipped MBTiles vector tile '{layer.name()}' (style-only mode)", "warning")
                        continue
                    if not url or not os.path.exists(url):
                        msg = "MBTiles file not found"
                        self.log_message.emit(f"  Skipped '{layer.name()}' ({msg})", "warning")
                        self._failed_layers.append((layer.name(), msg))
                        continue
                    pm_out = os.path.join(output_dir, "data", f"{name}.pmtiles")
                    ok, err = self._run_cmd(["pmtiles", "convert", url, pm_out])
                    if not ok:
                        self.log_message.emit(f"  MBTiles→PMTiles failed for '{layer.name()}': {err}", "error")
                        self._failed_layers.append((layer.name(), f"MBTiles→PMTiles failed: {err}"))
                        continue
                    self._maybe_verify(pm_out, layer.name())
                    sources[src_id] = {"type": "vector", "url": f"pmtiles://data/{name}.pmtiles"}
                    gl = (layer.customProperty("mapbox-gl-style")
                          or layer.customProperty("mapboxGLStyle")
                          or self._mbtiles_gl_style(url))
                    gl_layers = self._gl_layers_for_source(gl, src_id)
                    if gl_layers:
                        below.extend(gl_layers)
                        self._tile_groups.append({"name": layer.name(), "source": src_id})
                        self.log_message.emit(
                            f"  Bundled MBTiles vector tile '{layer.name()}' → PMTiles (offline)", "success")
                    else:
                        self.log_message.emit(
                            f"  Bundled '{layer.name()}' → PMTiles but found no GL style — "
                            f"add styling for source '{src_id}' in the target page.", "warning")
                        self._failed_layers.append(
                            (layer.name(), "MBTiles bundled without a GL style (unstyled)"))
                    continue

                if stype != "xyz" or not url:
                    msg = f"unsupported vector-tile source type '{stype}'"
                    self.log_message.emit(f"  Skipped vector tile '{layer.name()}' ({msg})", "warning")
                    self._failed_layers.append((layer.name(), msg))
                    continue
                gl = (layer.customProperty("mapbox-gl-style")
                      or layer.customProperty("mapboxGLStyle"))
                gl_layers = self._gl_layers_for_source(gl, src_id)
                style_glyphs = None
                if not gl_layers:
                    # No stored style — try the layer's own style URL (Carto, MapTiler, etc.
                    # store it as styleUrl= when the layer is added with a style).
                    style_url = self._style_url_from_vt(layer)
                    if style_url:
                        self.log_message.emit(
                            f"  Fetching GL style for '{layer.name()}' from {style_url}", "info")
                        fetched = self._fetch_gl_style(style_url)
                        if fetched:
                            gl_layers = self._gl_layers_for_source(fetched, src_id)
                            style_glyphs = fetched.get("glyphs")
                if gl_layers:
                    src = {"type": "vector", "tiles": [url]}
                    try:
                        zmin, zmax = layer.sourceMinZoom(), layer.sourceMaxZoom()
                        if zmin is not None and zmin >= 0:
                            src["minzoom"] = int(zmin)
                        if zmax is not None and zmax > 0:
                            src["maxzoom"] = int(zmax)
                    except Exception:
                        pass
                    sources[src_id] = src
                    below.extend(gl_layers)
                    self._tile_groups.append({"name": layer.name(), "source": src_id})
                    # If the output style has no glyphs yet, adopt the provider's so labels render.
                    if style_glyphs and not style_json.get("glyphs"):
                        style_json["glyphs"] = style_glyphs
                    self.log_message.emit(
                        f"  Styled vector tile '{layer.name()}' ({len(gl_layers)} layer(s))", "info")
                else:
                    # No GL style anywhere: MapLibre needs per-source-layer rules we can't infer,
                    # so the source would render nothing. Skip it (don't leave a dead source).
                    self.log_message.emit(
                        f"  Vector tile '{layer.name()}' has no style MapSplat can use — skipped. "
                        f"Add it in QGIS with a Style URL (or style it), or use the provider's raster "
                        f"(XYZ) tiles instead.", "warning")
                    self._failed_layers.append(
                        (layer.name(), "MVT vector tile has no usable style (skipped — needs a GL style)"))
            elif isinstance(layer, QgsRasterLayer):
                url = self._xyz_url_from_raster(layer)
                if not url:
                    msg = "could not read an XYZ {z}/{x}/{y} URL template (WMS/WMTS not supported)"
                    self.log_message.emit(f"  Skipped online raster '{layer.name()}' ({msg})", "warning")
                    self._failed_layers.append((layer.name(), msg))
                    continue
                sources[src_id] = {"type": "raster", "tiles": [url], "tileSize": 256}
                below.append({
                    "id": f"tile_{name}_raster",
                    "type": "raster",
                    "source": src_id,
                    "paint": {"raster-opacity": round(float(layer.opacity()), 3)},
                    "metadata": {"mapsplat:label": layer.name()},
                })
                self.log_message.emit(f"  Referenced online raster '{layer.name()}' (streams live)", "info")
        if below:
            arr = style_json.setdefault("layers", [])
            insert_at = 1 if (arr and arr[0].get("type") == "background") else 0
            arr[insert_at:insert_at] = below

    def _verify_pmtiles(self, pmtiles_path):
        """Run ``pmtiles verify`` on an output file (Story 14).

        :returns: (ok: bool, detail: str) — detail carries stderr on failure.
        """
        if not os.path.exists(pmtiles_path):
            return False, "file not found"
        try:
            result = subprocess.run(
                ["pmtiles", "verify", pmtiles_path],
                capture_output=True,
                text=True,
                timeout=600,
                startupinfo=STARTUPINFO,
                creationflags=CREATIONFLAGS,
            )
        except FileNotFoundError:
            return False, "pmtiles CLI not found"
        except subprocess.TimeoutExpired:
            return False, "verify timed out"
        except Exception as e:  # pragma: no cover - defensive
            return False, str(e)
        if result.returncode == 0:
            return True, ""
        detail = (result.stderr.strip() or result.stdout.strip()
                  or f"exit code {result.returncode}")
        # GDAL's PMTiles writer always stamps MinZoom=0 in the header, but tiny features only
        # produce tiles at a higher zoom — so `pmtiles verify` reports a zoom header/tile mismatch.
        # That is a benign metadata quirk (the archive reads fine), not corruption. Treat it as OK
        # (ok=True) but pass the detail back so it can be logged as a note rather than a failure.
        if "does not match min tile z" in detail or "does not match max tile z" in detail:
            return True, detail
        return False, detail

    def _maybe_verify(self, pmtiles_path, label):
        """Verify a written PMTiles file when the user enabled it; record failures.

        :returns: True if verification passed or was skipped, False on real corruption.
        """
        if not self.settings.get("verify_pmtiles"):
            return True
        ok, detail = self._verify_pmtiles(pmtiles_path)
        if ok and not detail:
            self.log_message.emit(f"  Verified {label}", "success")
        elif ok:
            # Benign zoom-header mismatch (GDAL writes MinZoom=0) — note it, don't fail.
            self.log_message.emit(
                f"  Verified {label} (benign header note: {detail.split(': ')[-1]})", "info")
        else:
            self.log_message.emit(f"  PMTiles verify FAILED for {label}: {detail}", "error")
            self._failed_layers.append((label, f"PMTiles verify failed: {detail}"))
        return ok

    def _merge_imported_style(self, style_json):
        """Merge imported style with generated style.

        :param style_json: Generated style dictionary
        :returns: Merged style dictionary
        """
        import_path = self.settings["imported_style_path"]
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                imported = json.load(f)

            # Generated sources are authoritative: they reflect exactly which layers are
            # selected for this export.  Keeping the imported style's sources would cause
            # 404s for any layers that were exported previously but are no longer selected.
            imported["sources"] = style_json.get("sources", {})

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
        """Check if the pmtiles CLI is available on PATH.

        Uses shutil.which so the check never depends on the exit code of
        'pmtiles --help', which varies across go-pmtiles versions.

        :returns: True if pmtiles is found on PATH
        """
        return shutil.which("pmtiles") is not None

    @staticmethod
    def basemap_cache_dir():
        """Directory for cached basemap extracts (under the active QGIS profile)."""
        try:
            from qgis.core import QgsApplication
            base = QgsApplication.qgisSettingsDirPath()
        except Exception:
            base = os.path.expanduser("~/.local/share/QGIS")
        cache = os.path.join(base, "mapsplat", "basemap_cache")
        try:
            os.makedirs(cache, exist_ok=True)
        except OSError:
            return None
        return cache

    @staticmethod
    def _basemap_cache_key(source, bbox_str, max_zoom):
        """Stable key for a basemap extract: source URL + extent + max zoom."""
        import hashlib
        raw = f"{source}|{bbox_str}|z{max_zoom}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _extract_basemap(self, output_dir, bounds):
        """Clip the basemap to the data bounding box via ``pmtiles extract``.

        Caches the result by (source, bbox, maxzoom): a cache hit copies the previous extract
        instead of re-downloading. Transient failures are retried up to 3×.

        :param output_dir: Export output directory
        :param bounds: [west, south, east, north] in EPSG:4326
        :returns: True if successful
        """
        import shutil

        source = self.settings["basemap_source"]
        output_path = os.path.join(output_dir, "data", "basemap.pmtiles")
        west, south, east, north = bounds
        bbox_str = f"{west},{south},{east},{north}"
        max_zoom = self.settings.get("max_zoom", 10)

        self.log_message.emit(f"  Basemap source: {source}", "info")
        self.log_message.emit(f"  Bounding box: {bbox_str}", "info")
        self.log_message.emit(f"  Max zoom: {max_zoom}", "info")
        self.log_message.emit(f"  Output: {output_path}", "info")

        cache_dir = self.basemap_cache_dir()
        cache_path = None
        if cache_dir:
            key = self._basemap_cache_key(source, bbox_str, max_zoom)
            cache_path = os.path.join(cache_dir, f"basemap_{key}.pmtiles")
            if os.path.exists(cache_path) and not self.settings.get("refresh_basemap_cache"):
                try:
                    shutil.copyfile(cache_path, output_path)
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    self.log_message.emit(
                        f"  Basemap cache HIT ({size_mb:.1f} MB) — skipped download", "success")
                    self.progress.emit(30)
                    return True
                except OSError as e:
                    self.log_message.emit(f"  Cache copy failed ({e}); re-extracting", "warning")

        self.log_message.emit("  Basemap cache miss — extracting", "info")
        threads = int(self.settings.get("basemap_download_threads", 4) or 4)
        ok = False
        for attempt in range(1, 4):
            if self._cancelled:
                self.log_message.emit("  Export cancelled by user.", "warning")
                return False
            if attempt > 1:
                self.log_message.emit(f"  Retrying basemap extract ({attempt}/3)...", "warning")
            ok, err = self._run_extract_once(source, output_path, bbox_str, max_zoom, threads)
            if ok:
                break
            self.log_message.emit(f"  pmtiles error: {err}", "error")
        if not ok:
            return False

        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            self.log_message.emit(f"  Basemap PMTiles size: {size_mb:.1f} MB", "info")
            if cache_path:
                try:
                    shutil.copyfile(output_path, cache_path)
                    self.log_message.emit("  Cached basemap extract for reuse", "info")
                except OSError:
                    pass
        return True

    def _run_extract_once(self, source, output_path, bbox_str, max_zoom, threads):
        """One ``pmtiles extract`` attempt. Returns (ok: bool, error: str)."""
        import time
        from qgis.PyQt.QtCore import QCoreApplication

        args = ["extract", source, output_path, f"--bbox={bbox_str}", f"--maxzoom={max_zoom}"]
        if threads and threads > 1:
            args.append(f"--download-threads={threads}")
        self.log_message.emit(f"  Command: pmtiles {' '.join(args)}", "info")

        # Drop a stale partial file from a previous attempt so size reporting is accurate.
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

        self._qprocess = QProcess()
        self._start_time = time.time()
        self._qprocess.start("pmtiles", args)

        if not self._qprocess.waitForStarted(10000):
            return False, "failed to start pmtiles"

        self.log_message.emit("  pmtiles extract started, waiting...", "info")
        last_update = time.time()
        while self._qprocess.state() != QProcess.ProcessState.NotRunning:
            QCoreApplication.processEvents()
            if self._cancelled:
                self._qprocess.kill()
                self._qprocess.waitForFinished(1000)
                return False, "cancelled"
            now = time.time()
            if now - last_update >= 3:
                last_update = now
                elapsed = now - self._start_time
                if os.path.exists(output_path):
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    self.log_message.emit(
                        f"  Extracting... {elapsed:.0f}s, output: {size_mb:.1f} MB", "info")
                else:
                    self.log_message.emit(f"  Extracting... {elapsed:.0f}s", "info")
            self._qprocess.waitForFinished(100)

        elapsed = time.time() - self._start_time
        exit_code = self._qprocess.exitCode()
        stderr = bytes(self._qprocess.readAllStandardError()).decode("utf-8", errors="replace")
        stdout = bytes(self._qprocess.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.log_message.emit(f"  pmtiles extract finished in {elapsed:.1f}s", "info")

        if exit_code != 0:
            return False, (stderr.strip() or stdout.strip() or f"exit code {exit_code}")
        return True, ""

    def _plugin_version(self):
        """Read the plugin version from metadata.txt (best-effort)."""
        try:
            meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")
            with open(meta, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("version="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return "unknown"

    def _dedupe_layer_ids(self, style_json):
        """Rename duplicate layer ids so MapLibre doesn't reject the whole style."""
        seen = set()
        renamed = 0
        for lay in style_json.get("layers", []):
            lid = lay.get("id")
            if lid in seen:
                new_id, n = lid, 2
                while new_id in seen:
                    new_id = f"{lid}__{n}"
                    n += 1
                lay["id"] = new_id
                renamed += 1
            seen.add(lay["id"])
        if renamed:
            self.log_message.emit(
                f"Renamed {renamed} duplicate layer id(s) to keep the style valid", "warning")

    def _prune_orphan_layers(self, style_json):
        """Remove style layers that reference a source not present in `sources`.

        MapLibre rejects the whole style if any layer points at a missing source, so a
        single stale/dangling layer would blank the entire map. Layers without a source
        (e.g. `background`) are always kept.
        """
        srcs = set(style_json.get("sources", {}).keys())
        layers = style_json.get("layers", [])
        kept = [ly for ly in layers if not ly.get("source") or ly.get("source") in srcs]
        dropped = len(layers) - len(kept)
        if dropped:
            style_json["layers"] = kept
            self.log_message.emit(
                f"Pruned {dropped} layer(s) referencing a missing source", "warning"
            )
        return style_json

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
        # Stream mode -> the remote PMTiles (read via HTTP range requests in the browser);
        # bundle mode -> the locally extracted file.
        if self.settings.get("basemap_mode", "bundle") == "stream":
            src_url = "pmtiles://" + self.settings.get("basemap_source", "").strip()
            src_desc = "remote URL (streamed)"
        else:
            src_url = "pmtiles://data/basemap.pmtiles"
            src_desc = "local file"
        for src_name, src in basemap.get("sources", {}).items():
            if src.get("type") == "vector" and src.get("url"):
                src["url"] = src_url
                self.log_message.emit(
                    f"  Updated basemap source '{src_name}' to {src_desc}", "info"
                )
                break

        # Optionally override the basemap's background colour. Default: leave the basemap's
        # supplied value unchanged; only override when the user set a background_color.
        bg = self.settings.get("background_color")
        if bg:
            for bl in basemap.get("layers", []):
                if bl.get("type") == "background":
                    bl.setdefault("paint", {})["background-color"] = bg

        # Remember the basemap's own sources (before business sources are merged in) so the viewer
        # can group all basemap layers under a collapsible "Basemap" section.
        self._basemap_sources = list(basemap.get("sources", {}).keys())

        # Inject business data sources
        basemap.setdefault("sources", {}).update(business_style_json.get("sources", {}))

        # Append business layers, skipping background (basemap provides its own)
        overlay_layers = [
            layer for layer in business_style_json.get("layers", [])
            if layer.get("id") != "background"
        ]
        basemap.setdefault("layers", []).extend(overlay_layers)

        # Preserve mapsplat hatch-pattern metadata so the viewer can load the images.
        biz_patterns = business_style_json.get("metadata", {}).get("mapsplat:patterns")
        if biz_patterns:
            basemap.setdefault("metadata", {})["mapsplat:patterns"] = biz_patterns
        # Preserve the legend-group structure so the viewer can show collapsible groups.
        biz_groups = business_style_json.get("metadata", {}).get("mapsplat:legend-groups")
        if biz_groups:
            basemap.setdefault("metadata", {})["mapsplat:legend-groups"] = biz_groups

        self.log_message.emit(
            f"  Merged {len(overlay_layers)} business layer(s) into basemap style", "info"
        )

        # Handle sprites. If the basemap already ships a sprite (shields/POI/arrow icons) AND we
        # have a business sprite, combine them via a MapLibre **sprite array** so both render: the
        # basemap keeps its icons under the default namespace, and our icons live in the "mapsplat"
        # namespace (icon-image references and the sprite-icons metadata are prefixed to match).
        # If the basemap has no sprite, just use ours directly.
        business_sprite = business_style_json.get("sprite")
        biz_icons = business_style_json.get("metadata", {}).get("mapsplat:sprite-icons", [])
        basemap_sprite = basemap.get("sprite")

        if business_sprite and basemap_sprite:
            default_entries = (basemap_sprite if isinstance(basemap_sprite, list)
                               else [{"id": "default", "url": basemap_sprite}])
            basemap["sprite"] = default_entries + [{"id": "mapsplat", "url": business_sprite}]
            names = set(biz_icons)
            for layer in overlay_layers:
                lay = layer.get("layout", {})
                if layer.get("type") == "symbol" and "icon-image" in lay:
                    lay["icon-image"] = self._prefix_icon_names(lay["icon-image"], "mapsplat:", names)
            if biz_icons:
                basemap.setdefault("metadata", {})["mapsplat:sprite-icons"] = \
                    ["mapsplat:" + n for n in biz_icons]
            self.log_message.emit(
                "  Combined basemap + business sprites (business icons namespaced 'mapsplat:')",
                "info",
            )
        elif business_sprite:
            basemap["sprite"] = business_sprite
            if biz_icons:
                basemap.setdefault("metadata", {})["mapsplat:sprite-icons"] = biz_icons
            self.log_message.emit("  Using local business sprite for icons", "info")

        return basemap

    def _prefix_icon_names(self, icon_image, prefix, names):
        """Recursively prefix known icon names in an ``icon-image`` value (string or expression).

        Only strings that are known business sprite icon names get the prefix, so category
        *labels* inside a match expression are left untouched.
        """
        if isinstance(icon_image, str):
            return prefix + icon_image if icon_image in names else icon_image
        if isinstance(icon_image, list):
            return [self._prefix_icon_names(e, prefix, names) for e in icon_image]
        return icon_image

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

        Checks in priority order:
        1. Pre-computed ``extent_bounds`` (e.g. captured from map canvas view).
        2. ``extent_layer_id`` — uses that layer's extent.
        3. Falls back to combined extent of all exported vector layers.

        :param layers: Dict with 'vector' list (fallback when no extent layer).
        :returns: [west, south, east, north] in EPSG:4326
        """
        if "extent_bounds" in self.settings:
            self.log_message.emit("Using map view extent for export bounds", "info")
            return self.settings["extent_bounds"]

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

    def _bounds_to_rect_3857(self, bounds):
        """Convert [W, S, E, N] in EPSG:4326 to a QgsRectangle in EPSG:3857.

        Used to pass a clip extent to QgsVectorFileWriter.SaveVectorOptions.filterExtent.
        filterExtent must be in the destination CRS (EPSG:3857) so QGIS can
        reverse-transform it to each layer's source CRS for feature filtering.
        """
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        west, south, east, north = bounds
        rect_4326 = QgsRectangle(west, south, east, north)
        transform = QgsCoordinateTransform(crs_4326, self.target_crs, self.project)
        return transform.transformBoundingBox(rect_4326)

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
            ("https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css", "maplibre-gl.css"),
            ("https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js", "maplibre-gl.js"),
            ("https://unpkg.com/pmtiles@4.4.1/dist/pmtiles.js", "pmtiles.js"),
        ]

        lib_dir = os.path.join(output_dir, "lib")
        try:
            import urllib.request
            for url, filename in assets:
                dest = os.path.join(lib_dir, filename)
                self.log_message.emit(f"  Downloading {filename}...", "info")
                if not url.startswith("https://"):          # defence in depth (URLs are literals)
                    raise ValueError(f"refusing non-https asset URL: {url}")
                urllib.request.urlretrieve(url, dest)  # nosec B310 - hardcoded https CDN URLs
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
import json
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

    def end_headers(self):
        """Disable browser caching so a re-export is always shown fresh (no stale
        style.json/index.html/tiles after re-generating the map)."""
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

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

    # Bind, auto-advancing the port if it's already in use (a stale server or a second
    # export), so we print a clean message instead of a raw "Address already in use".
    httpd = None
    for _candidate in range(PORT, PORT + 20):
        try:
            httpd = ThreadingHTTPServer((HOST, _candidate), RangeRequestHandler)
            PORT = _candidate
            break
        except OSError:
            print(f"Port {_candidate} is in use, trying {_candidate + 1}...")
    if httpd is None:
        print(f"No free port found in {args.port}-{args.port + 19}. Use --port <N> to pick one.")
        sys.exit(1)

    # Startup banner: announce exactly WHAT is being served, so a stale/wrong folder
    # (a common gotcha — e.g. a leftover server from a deleted export) is obvious.
    _dir = os.getcwd()  # serve.py chdir'd to its own folder above → this is the serving root
    print("=" * 64)
    print("MapSplat local server")
    print(f"  serve.py: {os.path.abspath(__file__)}")
    print(f"  Serving : {_dir}")
    if "Trash" in _dir or ".local/share/Trash" in _dir or "/.Trash" in _dir:
        print("  !! WARNING: this folder is in the TRASH — you are probably serving a")
        print("     DELETED export. cd to your real export folder and restart.")
    try:
        with open(os.path.join(_dir, "style.json"), "r", encoding="utf-8") as _f:
            _style = json.load(_f)
        _meta = _style.get("metadata", {}) or {}
        _srcs = sorted({L.get("source") for L in _style.get("layers", [])
                        if L.get("source") and L.get("source") != "protomaps"})
        print(f"  Project: {_meta.get('mapsplat:project') or _style.get('name') or '?'}"
              f"  (MapSplat {_meta.get('mapsplat:version', '?')})")
        print(f"  Layers : {len(_style.get('layers', []))} total; "
              f"{len(_srcs)} data source(s): {', '.join(_srcs) if _srcs else '(none)'}")
    except FileNotFoundError:
        print("  !! No style.json here — is this a MapSplat export folder?")
    except Exception as _e:
        print(f"  (could not read style.json: {_e})")
    print(f"  URL    : http://localhost:{PORT}")
    print("=" * 64)
    if HOST != "127.0.0.1":
        print(f"  (listening on {HOST}:{PORT})")
    print("Press Ctrl+C to stop (or close this window)\\n")

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
        return sanitized
