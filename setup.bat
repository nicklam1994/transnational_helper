@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   Teamwork Helper - Environment Setup
echo ==========================================
echo.

:: ---------- Step 0: stop services so files are not locked ----------
echo [0/5] Stopping running services, to avoid locked files ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*server.py*' -or $_.CommandLine -like '*keepalive_service.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 3 127.0.0.1 >nul
echo [OK] Services stopped
echo.

:: ---------- Step 1: find a suitable Python 3 ----------
echo [1/5] Looking for Python 3 - prefer 3.12 / 3.13 ...
set "PYTHON="
call :detect 3.12
call :detect 3.13
call :detect 3.11
call :detect 3.10
call :detect 3
if defined PYTHON goto :py_found
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%i"
:py_found
if not defined PYTHON goto :find_python_fail
for /f "delims=" %%v in ('"%PYTHON%" -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%v"
echo [OK] Python found: %PYTHON%
echo      Version: %PYVER%
echo.

:: ---------- Step 2: create / keep venv ----------
echo [2/5] Preparing virtual environment .venv ...
set "VENV_NEW="
if exist ".venv\Scripts\python.exe" goto :venv_ready
"%PYTHON%" -m venv .venv
if errorlevel 1 goto :venv_fail
set "VENV_NEW=1"
echo [OK] .venv created

:venv_ready
if defined VENV_NEW goto :venv_show
echo [OK] Existing .venv kept

:venv_show
".venv\Scripts\python.exe" -c "import sys; print('      venv Python:', sys.version.split()[0])"
echo.

:: ---------- Step 3: install packages ----------
echo [3/5] Installing packages ...
echo       flask, flask-cors, requests, playwright, PyPDF2, pywin32, pillow, pymupdf
".venv\Scripts\python.exe" -m pip install --no-cache-dir --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install --no-cache-dir --upgrade --only-binary=:all: flask flask-cors requests playwright PyPDF2 pywin32 pillow pymupdf==1.28.2
if errorlevel 1 goto :try_plain
echo [OK] Packages installed
goto :deps

:try_plain
echo.
echo [WARN] Wheel-only install failed, retrying without --only-binary ...
".venv\Scripts\python.exe" -m pip install --no-cache-dir --upgrade flask flask-cors requests playwright PyPDF2 pywin32 pillow pymupdf
if errorlevel 1 goto :install_fail
echo [OK] Packages installed

:: ---------- Step 4: verify, auto-repair if broken ----------
:deps
echo.
echo [4/5] Verifying dependencies, auto-repair if something is broken ...
echo.
".venv\Scripts\python.exe" check_deps.py
if errorlevel 1 goto :deps_fail
echo.

:: ---------- Step 5: done ----------
echo [5/5] Setup complete.
echo.
echo ==========================================
echo   Setup complete
echo ==========================================
echo.
echo Next steps:
echo   1. Double-click start_server.bat
echo   2. Edge will open the teamwork login page
echo   3. Log in with your account and OTP
echo   4. The app opens at http://localhost:5000
echo.
echo NOTE: this setup stopped any running services first. If the app was
echo       running before, double-click start_server.bat to start it again.
echo.
pause
exit /b 0


:find_python_fail
echo.
echo [ERROR] Python 3 not found.
echo Please install Python 3.12 or newer from:
echo   https://www.python.org/downloads/
echo IMPORTANT: tick "Add python.exe to PATH" during install.
echo.
pause
exit /b 1

:venv_fail
echo.
echo [ERROR] Failed to create the virtual environment.
echo Check disk space and permissions, then run setup.bat again.
echo.
pause
exit /b 1

:install_fail
echo.
echo [ERROR] Package installation failed.
echo Check your internet connection and try again.
echo.
pause
exit /b 1

:deps_fail
echo.
echo [ERROR] Dependency check failed. See the messages above.
echo Run repair_deps.bat to do a clean re-install.
echo.
pause
exit /b 1


:: ---------- helper: set PYTHON if this launcher version exists ----------
:detect
if defined PYTHON goto :eof
for /f "delims=" %%i in ('py -%~1 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%i"
goto :eof
