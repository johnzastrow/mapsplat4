"""
MapSplat - Config Manager

Pure-Python TOML-like config file reader/writer. No external dependencies.
Supports human-editable config files with comments.
"""

__version__ = "0.6.16"

import os

# Per-key comment strings for the writer
_COMMENTS = {
    "export": {
        "project_name": "Project name — used as the output subdirectory name",
        "output_folder": "Base output folder (absolute path)",
        "layer_names": "Layer names to export (must match layer names in the QGIS Layers panel)",
        "pmtiles_mode": 'PMTiles mode: "single" = all layers in one file, "separate" = one file per layer',
        "max_zoom": "Maximum tile zoom level (4–18)",
        "export_style_json": "Export a separate style.json file",
        "style_only": "Skip data export — regenerate HTML/style only",
        "imported_style_path": "Path to an external style.json to merge (leave blank to skip)",
        "write_log": "Write export log to export.log in the output folder",
        "bundle_offline": "Download MapLibre GL JS/CSS and PMTiles JS at export time for offline viewing",
        "extent_layer_name": "Layer name used to set the export extent; leave blank for full data extent",
    },
    "basemap": {
        "enabled": "Enable basemap overlay mode",
        "source_type": 'Source type: "url" or "file"',
        "source": "URL or local path to Protomaps .pmtiles",
        "style_path": "Path to Protomaps-compatible basemap style.json",
    },
    "viewer": {
        "scale_bar": "Controls shown in the HTML viewer",
        "geolocate": "Geolocate (show my location)",
        "fullscreen": "Fullscreen button",
        "coords": "Coordinate display (mouse position)",
        "zoom_display": "Zoom level display",
        "reset_view": "Reset view button (fit to data)",
        "north_reset": "North-up / reset rotation button",
        "label_placement_mode": "Label placement: 'exact' (match QGIS) or 'auto' (MapLibre avoids overlaps)",
        "advanced_legend": "Show per-category/class-break swatches and labels in the legend (true/false)",
        "map_width": "Map pixel width; 0 = responsive full-window",
        "map_height": "Map pixel height; 0 = responsive full-window",
    },
}

# Section key ordering
_SECTION_KEYS = {
    "export": [
        "project_name",
        "output_folder",
        "layer_names",
        "pmtiles_mode",
        "max_zoom",
        "export_style_json",
        "style_only",
        "imported_style_path",
        "write_log",
        "bundle_offline",
        "extent_layer_name",
    ],
    "basemap": [
        "enabled",
        "source_type",
        "source",
        "style_path",
    ],
    "viewer": [
        "scale_bar",
        "geolocate",
        "fullscreen",
        "coords",
        "zoom_display",
        "reset_view",
        "north_reset",
        "label_placement_mode",
        "advanced_legend",
        "map_width",
        "map_height",
    ],
}


def _toml_value(value):
    """Format a Python value as a TOML literal string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        items = ", ".join(f'"{_escape_string(v)}"' for v in value)
        return f"[{items}]"
    # String
    return f'"{_escape_string(str(value))}"'


def _escape_string(s):
    """Escape backslashes and double-quotes in a TOML string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_config(file_path, config_dict):
    """Write a config dict to a TOML file with comments.

    :param file_path: Absolute path to write to.
    :param config_dict: Nested dict with keys "export", "basemap", "viewer".
                        Each sub-dict maps string keys to values.
    :raises OSError: If the file cannot be written.
    """
    lines = [
        "# MapSplat Export Configuration",
        "# Edit this file to configure your export, then load it in QGIS.",
        "",
    ]

    for section in ("export", "basemap", "viewer"):
        section_data = config_dict.get(section, {})
        lines.append(f"[{section}]")
        key_order = _SECTION_KEYS.get(section, list(section_data.keys()))
        comments = _COMMENTS.get(section, {})

        first_key = True
        for key in key_order:
            if key not in section_data:
                continue
            comment = comments.get(key, "")
            if comment:
                if not first_key:
                    lines.append("")
                lines.append(f"# {comment}")
            value = section_data[key]
            lines.append(f"{key} = {_toml_value(value)}")
            first_key = False

        # Any extra keys not in the ordered list
        for key, value in section_data.items():
            if key not in key_order:
                lines.append(f"{key} = {_toml_value(value)}")

        lines.append("")

    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        if not lines[-1].endswith("\n"):
            fh.write("\n")


def read_config(file_path):
    """Read a TOML config file and return a nested dict.

    Sections map to top-level keys: "export", "basemap", "viewer".
    Value types are auto-detected: bool, int, string, list-of-strings.

    :param file_path: Absolute path to the config file.
    :returns: Nested dict ``{"export": {...}, "basemap": {...}, "viewer": {...}}``.
    :raises FileNotFoundError: If the file does not exist.
    :raises ValueError: On parse failure.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Config file not found: {file_path}")

    result = {}
    current_section = None

    with open(file_path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if current_section not in result:
                    result[current_section] = {}
                continue

            # Key = value
            if "=" in line:
                # Strip inline comments (# not inside a string)
                eq_idx = line.index("=")
                key = line[:eq_idx].strip()
                raw_value = line[eq_idx + 1:].strip()

                # Strip trailing inline comment if value is not a string
                if not raw_value.startswith('"') and not raw_value.startswith('['):
                    comment_idx = raw_value.find(" #")
                    if comment_idx != -1:
                        raw_value = raw_value[:comment_idx].strip()

                try:
                    value = _parse_value(raw_value)
                except ValueError as exc:
                    raise ValueError(
                        f"Parse error at line {lineno}: {raw_line.rstrip()!r} — {exc}"
                    ) from exc

                if current_section is not None:
                    result[current_section][key] = value
                # Keys outside any section are silently ignored
                continue

    return result


def _parse_value(raw):
    """Parse a raw TOML value string into a Python object."""
    # Boolean
    if raw == "true":
        return True
    if raw == "false":
        return False

    # Quoted string
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        inner = raw[1:-1]
        # Un-escape
        inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner

    # Array of quoted strings: ["a", "b"]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = []
        # Simple tokeniser — split on commas, strip whitespace/quotes
        for token in _split_array_tokens(inner):
            token = token.strip()
            if token.startswith('"') and token.endswith('"'):
                s = token[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                items.append(s)
            else:
                raise ValueError(f"Array item is not a quoted string: {token!r}")
        return items

    # Integer
    try:
        return int(raw)
    except ValueError:
        pass

    raise ValueError(f"Unrecognised value: {raw!r}")


def _split_array_tokens(inner):
    """Split array contents on top-level commas, respecting quoted strings."""
    tokens = []
    current = []
    in_string = False
    escape_next = False

    for ch in inner:
        if escape_next:
            current.append(ch)
            escape_next = False
        elif ch == "\\":
            current.append(ch)
            escape_next = True
        elif ch == '"':
            in_string = not in_string
            current.append(ch)
        elif ch == "," and not in_string:
            tokens.append("".join(current))
            current = []
        else:
            current.append(ch)

    if current:
        tokens.append("".join(current))

    return tokens
