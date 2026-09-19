@echo off
title Godot 2D Auto Spriter Dashboard
echo ========================================================
echo   Launching Godot 2D Auto Spriter ^& Rigger Dashboard...
echo ========================================================
cd /d "%~dp0"

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Launching with Python...
    python web_ui.py %*
    goto end
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Launching with Python Launcher...
    py web_ui.py %*
    goto end
)

if exist "dist\Godot2dAutoSpriterUI.exe" (
    echo [INFO] Standalone executable found at dist\Godot2dAutoSpriterUI.exe
    "dist\Godot2dAutoSpriterUI.exe" %*
    goto end
)

echo [ERROR] Neither standalone executable (dist\Godot2dAutoSpriterUI.exe) nor Python was found!
echo Please install Python 3.10+ and ensure it is added to PATH.
pause

:end

