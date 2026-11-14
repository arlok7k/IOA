@REM IOA — Windows build script
@REM Run this on a Windows machine with Python 3.11+ installed.
@REM It creates a standalone IOA.exe in the dist/ folder.

@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  IOA — Institute Outreach Automation
echo  Windows Build Script
echo ========================================
echo.

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.11+ for Windows.
    pause
    exit /b 1
)

echo [1/5] Installing build dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install PySide6 openpyxl python-dotenv python-telegram-bot pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

echo [2/5] Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist IOA.spec del IOA.spec >nul 2>&1

echo [3/5] Copying PyInstaller spec...
copy pyinstaller.spec IOA.spec >nul 2>&1

echo [4/5] Building IOA.exe (this may take a few minutes)...
pyinstaller --clean IOA.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [5/5] Verifying output...
if not exist "dist\IOA.exe" (
    echo [ERROR] IOA.exe was not created in dist/
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build completed successfully!
echo  Executable: dist\IOA.exe
echo  Installer instructions: see INSTALL.md
echo ========================================
pause
