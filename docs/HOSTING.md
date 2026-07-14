# Hosting & Self-Hosting Scope

MapSplat targets **static hosting**: everything it bundles is written as **PMTiles**, a single
cloud-optimized archive the browser reads with HTTP **Range requests**. A plain static server that
supports Range — **Caddy** (out of the box), nginx, `python serve.py`, S3+CloudFront — serves the
whole map with no tile-server process.

For Caddy/nginx configuration examples, see the [User Guide](USER_GUIDE.md).

## Bundled as PMTiles (fully self-hostable, works offline)

| Source | Handling |
|---|---|
| Your vector layers | `ogr2ogr → PMTiles` |
| Local raster layers (GeoTIFF, imagery, paletted) | `gdal → MBTiles → pmtiles convert` |
| Local **MBTiles** vector tiles | `pmtiles convert` (bundled) — raw MBTiles is SQLite and needs a tile server, so we convert it |
| Protomaps basemap (download & clip) | clipped **PMTiles** |

## Streams live — needs internet, NOT served by your host (marked 🌐 in the UI)

| Source | Why it can't be static-served |
|---|---|
| XYZ raster basemap / online XYZ raster layers | Tiles live on the **provider's** server; the browser fetches them cross-origin |
| Online **MVT** vector tile layers | Same — served by the provider |
| WMS / WMTS | Requires an OGC server |
| Streamed Protomaps basemap | The remote `.pmtiles` is fetched from its host, not yours |

> **Rule of thumb:** a raw MBTiles or any remote tile service can't be served by a plain web server.
> MapSplat converts local files to PMTiles so a static host can serve them; remote services are kept
> as live-streaming references (🌐) and clearly flagged — the export log notes any source that needs
> internet. Pulling remote services *into* the offline PMTiles bundle is a planned, terms-of-service-
> gated feature.

## Serving the map

The map needs HTTP **Range** requests (for PMTiles). Do **not** open `index.html` via `file://`.

- **Locally:** run `python serve.py` in the output folder (it handles Range) and open the printed
  `http://localhost:…` URL.
- **Production:** any Range-capable static host works. Set long cache headers on `data/*.pmtiles`
  (immutable) and short/no-cache on `index.html`/`style.json` — see the [User Guide](USER_GUIDE.md)
  for Caddy and nginx snippets.
