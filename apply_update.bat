@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Teamwork Helper - Apply Update
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" goto :no_env

echo [1/4] Stopping old services ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*keepalive_service.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 3 127.0.0.1 >nul
echo [OK] Old services stopped
echo.

echo [2/4] Checking dependencies, auto-install or repair if needed ...
if not exist "check_deps.py" goto :no_check
".venv\Scripts\python.exe" check_deps.py
if errorlevel 1 goto :deps_warn
echo [OK] Dependencies OK
goto :start_svc

:deps_warn
echo.
echo [WARN] Dependency check reported problems, see the messages above.
echo        The app will still start, but printing and auto-login may not work.
echo        Run repair_deps.bat to fix it, then restart.
echo.
ping -n 7 127.0.0.1 >nul
goto :start_svc

:no_check
echo [WARN] check_deps.py not found in this package - skipping dependency check.
echo        Run setup.bat once to install any new requirement.
echo.
ping -n 4 127.0.0.1 >nul

:start_svc
echo.
echo [3/4] Starting Keepalive Service ...
start "Keepalive Service" cmd /k "%~dp0.venv\Scripts\python.exe keepalive_service.py"
ping -n 3 127.0.0.1 >nul
echo [OK] Keepalive started
echo.

echo [4/4] Starting Teamwork Server ...
start "Teamwork Server" cmd /k "%~dp0.venv\Scripts\python.exe server.py"
ping -n 4 127.0.0.1 >nul
echo [OK] Server started
echo.

start "" "http://localhost:5000"

echo ==========================================
echo   Update applied
echo ==========================================
echo.
echo Tips:
echo  - Edge stays open, no re-login needed
echo  - If the page looks old, press Ctrl+F5
echo.
pause
exit /b 0


:no_env
echo [ERROR] Environment not found.
echo Please run setup.bat first.
echo.
pause
exit /b 1
