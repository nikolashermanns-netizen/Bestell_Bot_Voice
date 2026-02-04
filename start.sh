#!/bin/bash
# Bestell Bot Voice - Start Script (Unix/Git Bash)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Bestell Bot Voice - POC"
echo "========================================"
echo ""

# Prüfe Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python nicht gefunden!"
    echo "Bitte Python 3.11+ installieren."
    exit 1
fi

# Python-Befehl ermitteln
if command -v python3 &> /dev/null; then
    PYTHON=python3
else
    PYTHON=python
fi

echo "Python: $($PYTHON --version)"

# Virtual Environment prüfen/erstellen
if [ ! -d "venv" ]; then
    echo ""
    echo "Erstelle Virtual Environment..."
    $PYTHON -m venv venv
fi

# Virtual Environment aktivieren
echo "Aktiviere Virtual Environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

# Dependencies installieren (falls nötig)
if [ ! -f "venv/.deps_installed" ]; then
    echo ""
    echo "Installiere Dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch venv/.deps_installed
    echo "Dependencies installiert."
fi

# .env prüfen
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNUNG: .env Datei nicht gefunden!"
    echo "Erstelle .env aus .env.example..."
    cp .env.example .env
    echo ""
    echo "WICHTIG: Bitte .env bearbeiten und Credentials eintragen:"
    echo "  - OPENAI_API_KEY"
    echo "  - SIP_SERVER, SIP_USERNAME, SIP_PASSWORD"
    echo ""
    read -p "Drücke Enter um fortzufahren (oder Ctrl+C zum Abbrechen)..."
fi

# App starten
echo ""
echo "Starte Bestell Bot Voice..."
echo "----------------------------------------"
$PYTHON main.py
