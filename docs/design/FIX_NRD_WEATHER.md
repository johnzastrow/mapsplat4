# Fix: northredoubt.com/weather Map Controls Missing

**Date:** 2026-03-22
**Status:** Diagnosed, not yet fixed

---

## Symptoms

The map at `https://northredoubt.com/weather` loads and displays data correctly,
but none of the viewer controls configured in MapSplat are visible:

- No scale bar
- No geolocate button
- No fullscreen button
- No zoom level display
- No coordinate display
- No reset-view button
- No north-reset button
- No layer toggle panel / legend

---

## Infrastructure

| Component | Location | Status |
|---|---|---|
| Map data + style | `weathermap.fluidgrid.site` (serve.py on port 8000) | Working |
| Reverse proxy | Caddy on `recipe.fluidgrid.site` | Working |
| Embedding page | `northredoubt.com/weather` | Partial — map renders, controls missing |

**Note:** A separate 502 Bad Gateway issue was resolved on 2026-03-22. The Caddyfile
was proxying to port 8001 while serve.py was listening on port 8000, and had a
duplicate `reverse_proxy` directive. Both fixed; service is now healthy.

---

## Root Cause

The `northredoubt.com/weather` page was **hand-written**, not assembled from the
MapSplat-generated `BEGIN/END MAPSPLAT` embed blocks.

The author used a minimal map initialization pattern with an `absolutify()` helper
to rewrite source URLs to point at `weathermap.fluidgrid.site`, but wrote the JS
from scratch rather than copying from the demarcated section of
`weathermap.fluidgrid.site/index.html`. As a result:

- No `addControl()` calls were included
- The HTML elements the controls depend on (`#coords-display`, `#zoom-display`,
  `#reset-view`, `#north-reset`) are absent from the page
- `mousemove` writes to `#info` (raw JSON) instead of `#coords-display`

---

## What the MapSplat Demarcation Actually Contains

The `BEGIN/END MAPSPLAT` blocks in the generated `index.html` **do** cover
everything needed. The demarcation was not the problem.

**Head block** (`BEGIN MAPSPLAT <head>`) contains:
- MapLibre GL CSS and JS (CDN or local)
- PMTiles JS
- All CSS for info panel, layer toggles, legend swatches, and custom controls

**Body block** (`BEGIN MAPSPLAT <body>`) contains:
- `#map-container` and `#map` divs
- Info panel with layer toggle list
- HTML elements for all enabled controls:
  - `{coords_html}` → coordinate display element
  - `{zoom_html}` → zoom level display element
  - `{reset_view_html}` → reset-view button
  - `{north_reset_html}` → north-reset button
- Full `<script>` block including:
  - PMTiles protocol registration
  - Map initialization
  - `NavigationControl`, `ScaleControl`, `GeolocateControl`, `FullscreenControl`
  - `fitBounds` on load
  - Layer toggle and legend building logic
  - `styleimagemissing` handler
  - Click popup handler
  - Coordinate display, zoom display, reset-view, north-reset wiring

---

## The Fix

The hand-written JS in `northredoubt.com/weather` needs to be replaced with the
content of the `BEGIN/END MAPSPLAT` blocks from
`weathermap.fluidgrid.site/index.html`, with one adaptation: the style fetch must
use the `absolutify()` pattern to rewrite relative URLs to point at
`weathermap.fluidgrid.site`.

### Step 1 — Get the current embed blocks

View source of `https://weathermap.fluidgrid.site/index.html` and copy:
- Everything between `BEGIN MAPSPLAT: copy the lines below into your page <head>`
  and `END MAPSPLAT <head> section`
- Everything between `BEGIN MAPSPLAT: copy the lines below into your page <body>`
  and `END MAPSPLAT <body> section` (if present), or to the closing `</script>`

### Step 2 — Adapt the style fetch

The generated index.html fetches style inline:
```javascript
fetch('./style.json').then(r => r.json()).then(function(mapStyle) {
    const map = new maplibregl.Map({ style: mapStyle, ... });
    ...
});
```

Replace with the `absolutify()` pattern already working in the page:
```javascript
const WEATHERMAP_BASE = 'https://weathermap.fluidgrid.site/';

function absolutify(url) {
    if (!url || url.startsWith('http') || url.startsWith('//')) return url;
    if (url.startsWith('pmtiles://'))
        return 'pmtiles://' + WEATHERMAP_BASE + url.slice('pmtiles://'.length);
    return WEATHERMAP_BASE + url;
}

fetch(WEATHERMAP_BASE + 'style.json')
    .then(function(r) { return r.json(); })
    .then(function(style) {
        for (var key in style.sources) {
            var src = style.sources[key];
            if (src.url) src.url = absolutify(src.url);
        }
        if (style.sprite) style.sprite = absolutify(style.sprite);
        if (style.glyphs) style.glyphs = absolutify(style.glyphs);
        return style;
    })
    .then(function(mapStyle) {
        // -- paste the rest of the MapSplat body script block here --
    });
```

### Step 3 — Add the control HTML elements to the page body

The JS wires up controls by ID. The corresponding HTML elements must exist in the
page. Copy the `#map-container` div (including the info panel and all control
elements) from the body BEGIN MAPSPLAT block into the `northredoubt.com/weather`
page at the location where the map should appear.

### Step 4 — Add the CSS

Copy the `<style>` block from the head BEGIN MAPSPLAT block into the
`northredoubt.com/weather` page `<head>`. Without it, the info panel, layer
toggles, and legend swatches will be unstyled.

---

## Checklist

- [ ] Copy head CSS block from `weathermap.fluidgrid.site/index.html` → `northredoubt.com/weather <head>`
- [ ] Replace hand-written map JS with MapSplat body script block
- [ ] Adapt style fetch to use `absolutify()` pattern
- [ ] Verify `#map-container`, `#coords-display`, `#zoom-display`, `#reset-view`, `#north-reset` elements exist in page
- [ ] Verify map controls appear after fix
- [ ] Verify layer toggle panel appears
- [ ] Verify coordinate display and zoom display update on interaction
- [ ] Verify reset-view and north-reset buttons work
