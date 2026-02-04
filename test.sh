#!/bin/bash
# Bestell Bot Voice - Test Script (Unix/Git Bash)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Bestell Bot Voice - Tests"
echo "========================================"
echo ""

# Virtual Environment aktivieren
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo "WARNUNG: Virtual Environment nicht gefunden."
    echo "Bitte zuerst ./start.sh ausführen."
    exit 1
fi

# Tests ausführen
echo "Führe Komponenten-Tests aus..."
echo "----------------------------------------"
python test_app.py

echo ""
echo "----------------------------------------"
echo "Tests abgeschlossen."
