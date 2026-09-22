@echo off
chcp 65001 >nul
setlocal
set "SYS32=%SystemRoot%\System32"

echo ==========================================
echo   Install Visual C++ 2015-2022 Runtime x64
echo ==========================================
echo.
echo Needed by PyMuPDF and pywin32. A fresh Windows install often
echo lacks it, which shows up as:
echo   ImportError: DLL load failed while importing _extra
echo.
echo This downloads about 25 MB and installs silently.
echo A Windows UAC prompt will appear - click Yes.
echo.
pause

set "EXE=%TEMP%\vc_redist.x64.exe"

echo [1/3] Downloading ...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $env:TEMP\vc_redist.x64.exe -UseBasicParsing; Write-Host 'downloaded OK' } catch { Write-Host 'download failed'; exit 1 }"
if errorlevel 1 goto :dl_fail
if not exist "%EXE%" goto :dl_fail

echo.
echo [2/3] Installing. Click Yes on the UAC prompt ...
powershell -NoProfile -Command "Start-Process -FilePath $env:TEMP\vc_redist.x64.exe -ArgumentList '/install','/quiet','/norestart' -Verb RunAs -Wait"
echo Installer finished.

echo.
echo [3/3] Verifying ...
set "MISS="
if not exist "%SYS32%\msvcp140.dll" set "MISS=1"
if not exist "%SYS32%\vcruntime140.dll" set "MISS=1"
if not exist "%SYS32%\vcruntime140_1.dll" set "MISS=1"
if defined MISS goto :incomplete

echo [OK] VC++ runtime is installed now.
echo.
echo Next step: run repair_deps.bat to re-check everything,
echo or just start_server.bat to start the app.
echo.
pause
exit /b 0


:incomplete
echo.
echo [WARN] Some runtime files are still missing.
echo        Please REBOOT Windows, then run repair_deps.bat again.
echo.
pause
exit /b 1


:dl_fail
echo.
echo [ERROR] Could not download the installer.
echo Please download it manually and run it:
echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
echo.
pause
exit /b 1
