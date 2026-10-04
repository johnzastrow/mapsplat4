"""
MapSplat - Protomaps basemap helpers

Pure-Python helpers for the Basemap Overlay options: the built-in Protomaps styles shipped with
the plugin, finding the latest daily Protomaps build, and composing the ``pmtiles extract``
command for an export area. No QGIS imports, so everything here is unit-testable.
"""

__version__ = "0.45.0"

import json
import os

# Protomaps publishes a daily planet build and keeps the past week of them (plus the latest build
# of each patch version), so a dated build URL stops working within days.
PROTOMAPS_BUILDS_JSON = "https://build-metadata.protomaps.dev/builds.json"
PROTOMAPS_BUILD_BASE = "https://build.protomaps.com/"
PROTOMAPS_BUILDS_PAGE = "https://maps.protomaps.com/builds/"
PMTILES_CLI_RELEASES = "https://github.com/protomaps/go-pmtiles/releases"

# The basemap guide: bundled with the plugin, and the same file published via GitHub Pages.
GUIDE_RELATIVE_PATH = os.path.join("help", "basemaps.html")
GUIDE_ONLINE_URL = "https://johnzastrow.github.io/mapsplat4/basemaps.html"

# Built-in styles generated from @protomaps/basemaps (scripts/gen_basemap_styles.mjs).
# Display name -> flavor id; the file is basemap_styles/protomaps-<flavor>.json.
BUILTIN_FLAVORS = {
    "Protomaps Light": "light",
    "Protomaps Dark": "dark",
    "Protomaps White": "white",
    "Protomaps Grayscale": "grayscale",
    "Protomaps Black": "black",
}
CUSTOM_STYLE_LABEL = "Custom style.json..."
DEFAULT_FLAVOR = "light"


# build.protomaps.com only lets its own viewer (maps.protomaps.com) read builds from a browser:
# it sends no Access-Control-Allow-Origin for any other site and refuses CORS preflights. So a
# published map cannot STREAM a daily build; it must be downloaded and clipped instead.
PROTOMAPS_BUILD_HOST = "build.protomaps.com"
# Any foreign origin works for probing whether a server lets other sites read a file.
CORS_PROBE_ORIGIN = "https://mapsplat.invalid"
# Some tile hosts (build.protomaps.com among them) answer Python's default urllib user agent with
# HTTP 403, which made valid URLs look unreachable. Identify as MapSplat instead.
USER_AGENT = f"MapSplat/{__version__} (QGIS plugin; +https://github.com/johnzastrow/mapsplat4)"


def is_protomaps_daily_build(url):
    """True if *url* points at a Protomaps daily build (which browsers cannot stream)."""
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url.strip()).hostname or "").lower() == PROTOMAPS_BUILD_HOST
    except (AttributeError, ValueError):
        return False


def allows_cross_origin(allow_origin_header, origin=CORS_PROBE_ORIGIN):
    """True if an ``Access-Control-Allow-Origin`` response value lets *origin* read the file."""
    value = (allow_origin_header or "").strip()
    return value == "*" or value == origin


def builtin_style_path(flavor, plugin_dir):
    """Path of the shipped style JSON for a built-in flavor id (e.g. ``"light"``).

    :raises ValueError: if *flavor* is not one of the built-in flavors.
    """
    if flavor not in BUILTIN_FLAVORS.values():
        raise ValueError(f"unknown Protomaps flavor: {flavor!r}")
    return os.path.join(plugin_dir, "basemap_styles", f"protomaps-{flavor}.json")


def latest_build_url(builds_json):
    """Return the URL of the newest Protomaps daily build from the builds.json payload.

    :param builds_json: the response body (bytes or str): a JSON list of objects with a
                        ``key`` such as ``"20261003.pmtiles"``.
    :returns: e.g. ``"https://build.protomaps.com/20261003.pmtiles"``
    :raises ValueError: if the payload is not the expected list or holds no build.
    """
    if isinstance(builds_json, bytes):
        builds_json = builds_json.decode("utf-8")
    try:
        builds = json.loads(builds_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"builds list is not JSON: {e}") from e
    if not isinstance(builds, list):
        raise ValueError("builds list is not a JSON array")
    # Keys are YYYYMMDD.pmtiles, so the lexically largest is the newest. Only accept keys of
    # that exact shape, so nothing unexpected is pasted into the source field.
    keys = [b.get("key") for b in builds if isinstance(b, dict)]
    keys = [k for k in keys if isinstance(k, str) and len(k) == 16 and k[:8].isdigit() and k.endswith(".pmtiles")]
    if not keys:
        raise ValueError("no builds found in the list")
    return PROTOMAPS_BUILD_BASE + max(keys)


# Web Mercator covers longitudes -180..180 and latitudes -85.0511..85.0511. A map-view extent can run
# past those when zoomed far out; pmtiles does not reject such a box but clips the wrong area.
WEB_MERCATOR_MAX_LAT = 85.0511


def clamp_bounds(bounds):
    """Clamp [west, south, east, north] (EPSG:4326) to the Web Mercator world."""
    west, south, east, north = (float(v) for v in bounds)
    lat = WEB_MERCATOR_MAX_LAT
    return [max(west, -180.0), max(south, -lat), min(east, 180.0), min(north, lat)]


def extract_command(source, bounds, max_zoom, output="basemap.pmtiles"):
    """Compose the ``pmtiles extract`` command MapSplat runs for an export area.

    Matches the exporter's own call (``exporter.MapSplatExporter._run_extract_once``), so a
    file extracted with this command can be used as a local basemap source.

    :param source: Protomaps build URL or local .pmtiles path
    :param bounds: [west, south, east, north] in EPSG:4326 (already expanded by the caller)
    :param max_zoom: highest zoom level to keep
    :param output: output file name
    :returns: a single command line; arguments containing spaces are double-quoted
    """
    west, south, east, north = (round(v, 6) for v in clamp_bounds(bounds))
    if not (west < east and south < north):
        raise ValueError("bounds must be [west, south, east, north] with west < east, south < north")

    def q(arg):
        return f'"{arg}"' if any(c.isspace() for c in arg) else arg

    return f"pmtiles extract {q(source)} {q(output)} --bbox={west},{south},{east},{north} --maxzoom={int(max_zoom)}"
