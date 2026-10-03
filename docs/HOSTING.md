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

## Streams live — needs internet, NOT served by your host (shown with an online tag in the UI)

| Source | Why it can't be static-served |
|---|---|
| XYZ raster basemap / online XYZ raster layers | Tiles live on the **provider's** server; the browser fetches them cross-origin |
| Online **MVT** vector tile layers | Same — served by the provider |
| WMS / WMTS | Requires an OGC server |
| Streamed Protomaps basemap | The remote `.pmtiles` is fetched from its host, not yours. That host must allow CORS; Protomaps' daily builds do not, so use *Download & clip* for them |
| Basemap labels and icons (built-in styles) | Fonts and sprites load from `protomaps.github.io`, even with a clipped basemap. Self-host them with a custom style for a fully offline map (see the [basemap guide](https://johnzastrow.github.io/mapsplat4/basemaps.html#styles)) |

> **Rule of thumb:** a raw MBTiles or any remote tile service can't be served by a plain web server.
> MapSplat converts local files to PMTiles so a static host can serve them; remote services are kept
> as live-streaming references and clearly flagged — the export log notes any source that needs
> internet. Pulling remote services *into* the offline PMTiles bundle is a planned, terms-of-service-
> gated feature.

## Hosting a streamable basemap

To use *Stream from URL* with your own PMTiles basemap, host the file on a Range-capable server or
bucket and send these CORS headers for it:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Range
Access-Control-Expose-Headers: Content-Range, Content-Length, ETag
```

The plugin's **Test** button reports whether a URL allows this. See the
[Protomaps cloud storage guide](https://docs.protomaps.com/pmtiles/cloud-storage) for S3, R2 and GCS.

## Serving the map

The map needs HTTP **Range** requests (for PMTiles). Do **not** open `index.html` via `file://`.

- **Locally:** run `python serve.py` in the output folder (it handles Range) and open the printed
  `http://localhost:…` URL.
- **Production:** any Range-capable static host works. Set long cache headers on `data/*.pmtiles`
  (immutable) and short/no-cache on `index.html`/`style.json` — see the [User Guide](USER_GUIDE.md)
  for Caddy and nginx snippets.
