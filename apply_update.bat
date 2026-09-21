@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Teamwork Helper - Apply Update
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Environment not found.
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

echo [1/3] Stopping old services...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*keepalive_service.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Old services stopped

echo.
echo [2/3] Starting Keepalive Service...
start "Keepalive Service" cmd /k "%~dp0.venv\Scripts\python.exe keepalive_service.py"
timeout /t 2 /nobreak >nul
echo [OK] Keepalive started

echo.
echo [3/3] Starting Teamwork Server...
start "Teamwork Server" cmd /k "%~dp0.venv\Scripts\python.exe server.py"
timeout /t 3 /nobreak >nul
echo [OK] Server started

start "" "http://localhost:5000"

echo.
echo ==========================================
echo   Update applied!
echo ==========================================
echo.
echo Tips:
echo  - Edge stays open, no re-login needed
echo  - If the page looks old, press Ctrl+F5
echo.
pause
