@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Teamwork Helper - Start All Services
echo ==========================================
echo.

:: ---------- Find Edge (different install locations) ----------
set "EDGE="
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if not defined EDGE (
    echo [ERROR] Microsoft Edge not found.
    echo Install Edge or edit start_server.bat EDGE path.
    echo.
    pause
    exit /b 1
)

:: ---------- Check venv ----------
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Environment not set up yet.
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

echo [1/5] Closing existing Edge...
tasklist | findstr /i "msedge.exe" >nul
if %errorlevel% equ 0 (
    taskkill /F /IM msedge.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo [OK] Edge closed
) else (
    echo [OK] Edge not running, skip close
)

echo.
echo [2/5] Starting Edge debug mode (port 9222)...
start "" "%EDGE%" --remote-debugging-port=9222 --user-data-dir="%TEMP%\edge-debug" "https://hk-teamwork.transnational-grp.com/"
timeout /t 3 /nobreak >nul
echo [OK] Edge started with debug mode

echo.
echo [3/5] Starting Keepalive Service...
start "Keepalive Service" cmd /k "%~dp0.venv\Scripts\python.exe keepalive_service.py"
timeout /t 2 /nobreak >nul
echo [OK] Keepalive started

echo.
echo [4/5] Starting Teamwork Server...
start "Teamwork Server" cmd /k "%~dp0.venv\Scripts\python.exe server.py"
timeout /t 2 /nobreak >nul
echo [OK] Server started

echo.
echo [5/5] Opening browser...
start "" "http://localhost:5000"

echo.
echo ==========================================
echo [DONE] All services started!
echo ==========================================
echo.
echo Dev tip: use restart_server.bat to restart
echo only the Teamwork Server (keepalive and
echo browser stay untouched).
echo.
pause
