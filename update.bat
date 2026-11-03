@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo    Proxy Nodes  -  One Click Update
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 goto NOPYTHON

python update.py %*
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" goto FAILED

echo [DONE] You can close this window.
goto END

:NOPYTHON
echo [FAIL] python not found in PATH. Install Python first.
set RC=1
goto END

:FAILED
echo [FAIL] Exit code %RC%. Read the messages above.

:END
echo.
pause
