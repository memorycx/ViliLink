@echo off
setlocal
cd /d "%~dp0"

rem Usage: build.bat [onefile|onedir]

where python >nul 2>nul
if errorlevel 1 (
    py -3.11 tools\build.py %*
) else (
    python tools\build.py %*
)

if errorlevel 1 (
    echo.
    echo Build failed.
    exit /b 1
)
