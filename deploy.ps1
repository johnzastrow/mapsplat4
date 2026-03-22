# MapSplat Plugin Deployment Script for Windows (PowerShell)
# Deploys the plugin to QGIS 3.x plugins directory

$PluginName = "mapsplat"
$QgisDir = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins"
$TargetDir = "$QgisDir\$PluginName"

Write-Host "Deploying MapSplat to $TargetDir" -ForegroundColor Cyan

# Create directories
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\templates" | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\lib" | Out-Null

# Python files to copy
$PyFiles = @(
    "__init__.py",
    "mapsplat.py",
    "mapsplat_dockwidget.py",
    "exporter.py",
    "style_converter.py"
)

# Extra files to copy
$Extras = @(
    "metadata.txt",
    "icon.png",
    "resources.qrc"
)

# Copy Python files
Write-Host "Copying Python files..." -ForegroundColor Yellow
foreach ($file in $PyFiles) {
    if (Test-Path $file) {
        Copy-Item $file -Destination $TargetDir -Force
        Write-Host "  $file" -ForegroundColor Gray
    }
}

# Copy extras
Write-Host "Copying metadata and resources..." -ForegroundColor Yellow
foreach ($file in $Extras) {
    if (Test-Path $file) {
        Copy-Item $file -Destination $TargetDir -Force
        Write-Host "  $file" -ForegroundColor Gray
    }
}

# Copy resources.py if it exists
if (Test-Path "resources.py") {
    Copy-Item "resources.py" -Destination $TargetDir -Force
    Write-Host "  resources.py" -ForegroundColor Gray
}

# Copy templates if they exist
if (Test-Path "templates\*") {
    Copy-Item "templates\*" -Destination "$TargetDir\templates" -Recurse -Force
    Write-Host "  templates\" -ForegroundColor Gray
}

# Copy lib if it exists
if (Test-Path "lib\*") {
    Copy-Item "lib\*" -Destination "$TargetDir\lib" -Recurse -Force
    Write-Host "  lib\" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done! Plugin deployed to:" -ForegroundColor Green
Write-Host $TargetDir -ForegroundColor White
Write-Host ""
Write-Host "Restart QGIS and enable MapSplat in Plugin Manager." -ForegroundColor Cyan
