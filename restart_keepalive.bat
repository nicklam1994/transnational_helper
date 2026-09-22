@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Restart Keepalive Service
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Environment not set up yet.
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

:: Find and kill old keepalive process
echo [1/3] Stopping old keepalive...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*keepalive_service.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host \"Killed PID $($_.ProcessId)\" }"
ping -n 3 127.0.0.1 >nul
echo [OK] Old keepalive stopped

:: Start new keepalive
echo.
echo [2/3] Starting new keepalive...
start "Keepalive Service" cmd /k "%~dp0.venv\Scripts\python.exe keepalive_service.py"
ping -n 3 127.0.0.1 >nul
echo [OK] Keepalive started

echo.
echo [3/3] Done!
echo Keepalive Service restarted.
echo.
pause
