@REM IOA — Institute Outreach Automation
@REM Windows startup script
@REM This script creates a virtual environment (if missing), installs dependencies,
@REM and launches the IOA desktop application.
@REM Run by double-clicking this file on Windows.

@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  IOA — Institute Outreach Automation
echo  Windows Startup Script
echo ========================================
echo.

REM --- Check if Python is available ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.11 or newer from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/4] Python found.

REM --- Determine script directory (where run_windows.bat is located) ---
set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash for consistency
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo [2/4] Project directory: %SCRIPT_DIR%

REM --- Create virtual environment if it does not exist ---
if not exist "%SCRIPT_DIR%\.venv\python.exe" (
    echo [3/4] Creating virtual environment (.venv)...
    python -m venv "%SCRIPT_DIR%\.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [3/4] Virtual environment already exists.
)

REM --- Install / upgrade dependencies ---
echo [4/4] Installing dependencies from requirements.txt...
"%SCRIPT_DIR%\.venv\python.exe" -m pip install --upgrade pip >nul 2>&1
"%SCRIPT_DIR%\.venv\python.exe" -m pip install -r "%SCRIPT_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

REM --- Launch the application ---
echo.
echo ========================================
echo  Launching IOA...
echo ========================================
echo.
"%SCRIPT_DIR%\.venv\python.exe" "%SCRIPT_DIR%\main.py"

REM --- Keep window open if error ---
if errorlevel 1 (
    echo.
    echo [ERROR] IOA application exited with an error.
    pause
)

endlocal
