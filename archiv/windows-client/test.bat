@echo off
REM Bestell Bot Voice - Test Script (Windows)

cd /d "%~dp0"

echo ========================================
echo   Bestell Bot Voice - Tests
echo ========================================
echo.

REM Virtual Environment aktivieren
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo WARNUNG: Virtual Environment nicht gefunden.
    echo Bitte zuerst start.bat ausfuehren.
    pause
    exit /b 1
)

REM Tests ausfuehren
echo Fuehre Komponenten-Tests aus...
echo ----------------------------------------
python test_app.py

echo.
echo ----------------------------------------
echo Tests abgeschlossen.
pause
