@echo off

setlocal enabledelayedexpansion

cd /d "%~dp0"



echo ==========================================

echo   Teamwork Helper - Environment Setup

echo ==========================================

echo.



:: ---------- Step 1: Find Python 3 ----------

echo [1/4] Looking for Python 3...

set "PYTHON="



for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%i"

if not defined PYTHON (

    for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%i"

)

if not defined PYTHON (

    echo.

    echo [ERROR] Python 3 not found.

    echo Please install Python 3.10 or newer from:

    echo   https://www.python.org/downloads/

    echo IMPORTANT: tick "Add python.exe to PATH" during install.

    echo.

    pause

    exit /b 1

)

echo [OK] Python found: %PYTHON%



:: ---------- Step 2: Create venv ----------

echo.

echo [2/4] Creating virtual environment (.venv)...

if not exist ".venv\Scripts\python.exe" (

    "%PYTHON%" -m venv .venv

    if errorlevel 1 (

        echo [ERROR] Failed to create venv

        pause

        exit /b 1

    )

)

echo [OK] venv ready



:: ---------- Step 3: Install packages ----------

echo.

echo [3/4] Installing packages (flask, requests, playwright, PyPDF2, PyMuPDF, pywin32, pillow)...
".venv\Scripts\python.exe" -m pip install --no-cache-dir --upgrade pip
if errorlevel 1 goto :install_fail
".venv\Scripts\python.exe" -m pip install --no-cache-dir flask flask-cors requests playwright PyPDF2 pymupdf pywin32 pillow
if errorlevel 1 goto :install_fail
echo [OK] Packages installed


:: ---------- Step 4: Verify ----------

echo.

echo [4/4] Verifying installation...

".venv\Scripts\python.exe" -c "import flask, requests, greenlet, PyPDF2; import fitz; import win32print, win32ui, win32con; from PIL import Image, ImageWin; from playwright.sync_api import sync_playwright; print('All imports OK')"

if errorlevel 1 goto :verify_fail

echo [OK] Everything installed successfully

echo.

echo ==========================================

echo   Setup complete!

echo ==========================================

echo.

echo Next steps:

echo   1. Double-click start_server.bat

echo   2. Edge will open the teamwork login page

echo   3. Log in with your account and OTP

echo   4. The app opens at http://localhost:5000

echo.

pause

exit /b 0



:install_fail

echo.

echo [ERROR] Package installation failed.

echo Check your internet connection and try again.

echo.

pause

exit /b 1



:verify_fail

echo.

echo [ERROR] Import check failed. Packages may be incomplete.

echo Try running setup.bat again.

echo.

pause

exit /b 1

