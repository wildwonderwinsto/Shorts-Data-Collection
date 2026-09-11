@echo off
echo ============================================================
echo    YOUTUBE SHORTS DATA COLLECTOR - INSTALLER
echo ============================================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10 or later from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)
echo.

REM Activate and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.
echo [OK] Dependencies installed.
echo.

REM Check for FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ============================================================
    echo [WARNING] FFmpeg is NOT installed or not in PATH.
    echo.
    echo FFmpeg is REQUIRED for frame extraction and preview grids.
    echo.
    echo Install FFmpeg using one of these methods:
    echo.
    echo   Option 1: winget install ffmpeg
    echo.
    echo   Option 2: Download from https://ffmpeg.org/download.html
    echo             Extract and add the bin folder to your PATH.
    echo.
    echo   Option 3: choco install ffmpeg  (if Chocolatey is installed)
    echo.
    echo After installing, restart this terminal and run install.bat again.
    echo ============================================================
) else (
    echo [OK] FFmpeg found.
)
echo.



echo ============================================================
echo    INSTALLATION COMPLETE
echo ============================================================
echo.
echo To start scanning, run:
echo   run.bat
echo.
echo Or use the command line:
echo   venv\Scripts\activate.bat
echo   python scan.py "https://www.youtube.com/@ChannelName"
echo.
pause
