# MapSplat Plugin Deployment Script for Windows (PowerShell)
# Copies the plugin into a QGIS 4 profile for local testing. Ships the same files as the
# release zip (scripts/build_plugin.sh); keep the two lists in step.
#   Usage: .\deploy.ps1                 # default profile
#          .\deploy.ps1 -Profile work   # another profile

param([string]$Profile = "default")

$PluginName = "mapsplat"
$QgisDir = "$env:APPDATA\QGIS\QGIS4\profiles\$Profile\python\plugins"
$TargetDir = "$QgisDir\$PluginName"

$Files = @(
    "__init__.py", "mapsplat.py", "mapsplat_dockwidget.py", "exporter.py", "style_converter.py",
    "config_manager.py", "log_utils.py", "basemap_helpers.py",
    "metadata.txt", "icon.png", "LICENSE",
    "help\MapSplat_User_Guide.pdf", "help\basemaps.html",
    "basemap_styles\protomaps-light.json", "basemap_styles\protomaps-dark.json",
    "basemap_styles\protomaps-white.json", "basemap_styles\protomaps-grayscale.json",
    "basemap_styles\protomaps-black.json", "basemap_styles\LICENSE-protomaps-basemaps.md"
)

Write-Host "Deploying MapSplat to $TargetDir" -ForegroundColor Cyan
$missing = 0
foreach ($file in $Files) {
    if (-not (Test-Path $file)) {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        $missing++
        continue
    }
    $dest = Join-Path $TargetDir $file
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item $file -Destination $dest -Force
    Write-Host "  $file" -ForegroundColor Gray
}
if ($missing -gt 0) {
    Write-Host "Deployment incomplete: $missing file(s) missing. Run from the repository root." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Done. Restart QGIS 4 and enable MapSplat in the Plugin Manager." -ForegroundColor Green
