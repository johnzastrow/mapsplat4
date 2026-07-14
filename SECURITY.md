# Security Policy

## Supported versions

Security fixes are applied to the latest released version. Older versions are not maintained.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than opening a public issue:

- Preferred: GitHub's **[Report a vulnerability](../../security/advisories/new)**
  (repository **Security** tab > **Advisories**), or
- Email the maintainer at `johnzastrow@users.noreply.github.com`.

Please include steps to reproduce and the affected version. You will receive an acknowledgement
within a few days. We ask that you allow a reasonable window to release a fix before public
disclosure.

## Scope

MapSplat is a QGIS plugin that shells out to GDAL/OGR and the `pmtiles` CLI and generates a static
web-map bundle. Relevant concerns include command execution, file-path handling, and the network
fetches used for basemaps. The plugin does not handle authentication or store credentials.
