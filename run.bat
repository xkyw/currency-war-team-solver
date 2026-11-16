@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

where python >nul 2>nul
if %errorlevel%==0 (
    python run_all.py %*
) else (
    py -3 run_all.py %*
)

echo.
pause
