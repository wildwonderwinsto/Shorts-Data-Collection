@echo off
REM Activate virtual environment and launch the scanner
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM If arguments were passed, use CLI mode; otherwise interactive mode
if "%~1"=="" (
    python scan.py
) else (
    python scan.py %*
)

pause
