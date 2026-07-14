# Limitations & Known Gaps

Current as of **v0.43.0**. See also [Features](FEATURES.md) and [Troubleshooting](TROUBLESHOOTING.md).

## General

- **No 3D** — extrusions, terrain, and 3D tiles are not supported.
- **Static snapshot** — the export is not live; re-export to pick up data changes.
- **Zoom range** — features are tiled up to the max zoom set at export time; re-export higher for
  more detail.
- **No authentication** — the viewer and `serve.py` serve files without access control.
- **`python -m http.server` won't work** — it doesn't reliably support HTTP Range requests; use the
  bundled `serve.py` or a proper web server (see [Hosting](HOSTING.md)).
- **Basemap bundle mode & raster export need the `pmtiles` CLI** on your PATH (Stream mode does not).

## Renderers

- **Rule-based** — simple filter rules convert; complex nested rules fall back to a default style.
- **Heatmap / point-cluster** renderers fall back to a simple default style.

## Rasters & tile services

- **Single-band / styled rasters (e.g. DEMs)** may not tile yet — RGB/RGBA and paletted rasters are
  supported. (Enable *Include raster layers*; needs GDAL's MBTiles driver.)
- **Online tile services stream live** — vector-tile (MVT) and XYZ/WMS layers tagged as online need
  internet in the viewer and aren't served by your own host. Downloading them into the offline PMTiles
  bundle is planned but not yet available. See [Hosting](HOSTING.md).
- **Unstyled vector tiles** — an MVT layer with no Mapbox-GL style (no Style URL and no stored style)
  is skipped, because MapLibre needs per-source-layer rules that can't be inferred.

## Opacity & transparency

- **Semi-transparent polygon fills are supported** when the transparency is set via the fill **colour
  alpha** (the alpha slider in QGIS's colour picker) — it becomes `fill-opacity`.
- **Layer-level opacity is not captured.** *Layer Properties → Rendering → Opacity* is a separate
  control MapSplat does not read. If polygons look more opaque in the viewer than in QGIS, move the
  transparency into the fill-colour alpha.

## Unsupported fill & symbol effects

These have no MapLibre GL Style equivalent, so the output differs from the QGIS canvas — convert to a
Simple Fill before exporting if fidelity matters:

- **Gradient fills** — exported as a solid fill (the darkest gradient-stop colour, by luminance).
- **Shape-burst fills** — same solid-colour approximation.
- **Line/point pattern fills** where a real pattern tile can't be built — semi-transparent solid.
- **Drop shadows, background shapes, callout lines** on labels — silently omitted.

## Icons

- **Single sprite sheet** — all custom icons share one sprite; icon names must be unique across
  exported layers. (A fetched provider style's icons/fonts aren't bundled, so its labels/icons may be
  partial when a separate basemap supplies the glyphs.)
