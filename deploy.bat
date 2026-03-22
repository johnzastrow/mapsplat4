@echo off
REM MapSplat Plugin Deployment Script for Windows
REM Deploys the plugin to QGIS 3.x plugins directory

setlocal

set PLUGINNAME=mapsplat
set QGISDIR=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins

echo Deploying MapSplat to %QGISDIR%\%PLUGINNAME%

REM Create plugin directory
if not exist "%QGISDIR%\%PLUGINNAME%" mkdir "%QGISDIR%\%PLUGINNAME%"
if not exist "%QGISDIR%\%PLUGINNAME%\templates" mkdir "%QGISDIR%\%PLUGINNAME%\templates"
if not exist "%QGISDIR%\%PLUGINNAME%\lib" mkdir "%QGISDIR%\%PLUGINNAME%\lib"

REM Copy Python files
echo Copying Python files...
copy /Y "__init__.py" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "mapsplat.py" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "mapsplat_dockwidget.py" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "exporter.py" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "style_converter.py" "%QGISDIR%\%PLUGINNAME%\"

REM Copy extras
echo Copying metadata and resources...
copy /Y "metadata.txt" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "icon.png" "%QGISDIR%\%PLUGINNAME%\"
copy /Y "resources.qrc" "%QGISDIR%\%PLUGINNAME%\"

REM Copy resources.py if it exists
if exist "resources.py" copy /Y "resources.py" "%QGISDIR%\%PLUGINNAME%\"

REM Copy templates if they exist
if exist "templates\*" xcopy /Y /E "templates\*" "%QGISDIR%\%PLUGINNAME%\templates\"

REM Copy lib if it exists
if exist "lib\*" xcopy /Y /E "lib\*" "%QGISDIR%\%PLUGINNAME%\lib\"

echo.
echo Done! Plugin deployed to:
echo %QGISDIR%\%PLUGINNAME%
echo.
echo Restart QGIS and enable MapSplat in Plugin Manager.

endlocal
