@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Teamwork Helper - Repair Dependencies
echo ==========================================
echo.
echo Use this when:
echo   - Printing stopped working
echo   - ImportError: DLL load failed while importing _extra
echo   - Import check failed during setup
echo.

if not exist ".venv\Scripts\python.exe" goto :no_env

echo [1/3] Stopping services, to unlock files ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*server.py*' -or $_.CommandLine -like '*keepalive_service.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 3 127.0.0.1 >nul
echo [OK] Services stopped
echo.

echo [2/3] Cleaning and re-installing PyMuPDF, then checking everything ...
echo       Downloads about 25 MB.
echo.
".venv\Scripts\python.exe" check_deps.py --repair
if errorlevel 1 goto :repair_fail
echo.
echo [3/3] Repair succeeded.
echo.
set "RESTART="
set /p RESTART="Restart the app now? Enter 1 for yes, 0 for no: "
if "%RESTART%"=="1" goto :do_restart
echo Skipped. Run start_server.bat when you are ready.
echo.
pause
exit /b 0

:do_restart
echo Starting services ...
start "Keepalive Service" cmd /k "%~dp0.venv\Scripts\python.exe keepalive_service.py"
ping -n 3 127.0.0.1 >nul
start "Teamwork Server" cmd /k "%~dp0.venv\Scripts\python.exe server.py"
ping -n 4 127.0.0.1 >nul
start "" "http://localhost:5000"
echo [OK] Services started
echo.
pause
exit /b 0


:no_env
echo [ERROR] .venv not found.
echo Please run setup.bat first.
echo.
pause
exit /b 1

:repair_fail
echo.
echo [ERROR] Repair did NOT fully succeed. See the messages above.
echo Please copy the whole output and send it to the developer.
echo.
pause
exit /b 1
