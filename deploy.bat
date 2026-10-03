@echo off
REM MapSplat Plugin Deployment Script for Windows (CMD)
REM Copies the plugin into a QGIS 4 profile for local testing. Ships the same files as the
REM release zip (scripts/build_plugin.sh); keep the two lists in step.
REM   Usage: deploy.bat            (default profile)
REM          deploy.bat work       (another profile)

setlocal
set PROFILE=%~1
if "%PROFILE%"=="" set PROFILE=default
set TARGET=%APPDATA%\QGIS\QGIS4\profiles\%PROFILE%\python\plugins\mapsplat

echo Deploying MapSplat to %TARGET%
if not exist "%TARGET%\help" mkdir "%TARGET%\help"
if not exist "%TARGET%\basemap_styles" mkdir "%TARGET%\basemap_styles"

set MISSING=0
for %%F in (__init__.py mapsplat.py mapsplat_dockwidget.py exporter.py style_converter.py
            config_manager.py log_utils.py basemap_helpers.py metadata.txt icon.png LICENSE
            help\MapSplat_User_Guide.pdf help\basemaps.html
            basemap_styles\protomaps-light.json basemap_styles\protomaps-dark.json
            basemap_styles\protomaps-white.json basemap_styles\protomaps-grayscale.json
            basemap_styles\protomaps-black.json basemap_styles\LICENSE-protomaps-basemaps.md) do (
    if exist "%%F" (
        copy /Y "%%F" "%TARGET%\%%F" >nul
        echo   %%F
    ) else (
        echo   MISSING: %%F
        set MISSING=1
    )
)

if "%MISSING%"=="1" (
    echo Deployment incomplete: run from the repository root.
    exit /b 1
)
echo.
echo Done. Restart QGIS 4 and enable MapSplat in the Plugin Manager.
endlocal
