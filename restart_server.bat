@echo off
setlocal
cd /d "%~dp0"

echo [DEV] Restarting Teamwork Server only...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Environment not set up yet.
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)

timeout /t 1 /nobreak >nul
echo [OK] Old server stopped

start "Teamwork Server" cmd /k "%~dp0.venv\Scripts\python.exe server.py"

timeout /t 2 /nobreak >nul
echo [OK] New server started
echo [OK] Refresh http://localhost:5000
echo.
pause
