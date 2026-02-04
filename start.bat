@echo off
REM Bestell Bot Voice - Start Script (Windows)

cd /d "%~dp0"

echo ========================================
echo   Bestell Bot Voice - POC
echo ========================================
echo.

REM Pruefe Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python nicht gefunden!
    echo Bitte Python 3.11+ installieren.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo Python: %%i

REM Virtual Environment pruefen/erstellen
if not exist "venv" (
    echo.
    echo Erstelle Virtual Environment...
    python -m venv venv
)

REM Virtual Environment aktivieren
echo Aktiviere Virtual Environment...
call venv\Scripts\activate.bat

REM Dependencies installieren (falls noetig)
if not exist "venv\.deps_installed" (
    echo.
    echo Installiere Dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo. > venv\.deps_installed
    echo Dependencies installiert.
)

REM .env pruefen
if not exist ".env" (
    echo.
    echo WARNUNG: .env Datei nicht gefunden!
    echo Erstelle .env aus .env.example...
    copy .env.example .env
    echo.
    echo WICHTIG: Bitte .env bearbeiten und Credentials eintragen:
    echo   - OPENAI_API_KEY
    echo   - SIP_SERVER, SIP_USERNAME, SIP_PASSWORD
    echo.
    pause
)

REM App starten
echo.
echo Starte Bestell Bot Voice...
echo ----------------------------------------
python main.py

REM Bei Fehler pausieren
if %ERRORLEVEL% neq 0 (
    echo.
    echo App beendet mit Fehlercode: %ERRORLEVEL%
    pause
)
