@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ====================================================================
echo   Many-Body Studio - Standalone CPU onedir Builder [Beta v1]
echo ====================================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment .venv was not found in %~dp0
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo [0/5] Ensuring latest razor-sharp icons are built...
python tools\build_icons.py

echo.
echo [1/5] Running standalone builder...
python tools\build_onedir_cpu.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Standalone build failed. Inspect error messages above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Standalone build completed successfully!
pause
