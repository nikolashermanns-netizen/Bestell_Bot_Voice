#!/bin/bash
# Start GUI für Bestell Bot Voice
# ================================

SCRIPT_DIR="$(dirname "$0")"
cd "$SCRIPT_DIR"

# Prüfe ob Python verfügbar ist
if ! command -v python &> /dev/null; then
    echo "Python nicht gefunden!"
    exit 1
fi

# Installiere Dependencies falls nötig
pip install -q -r gui/requirements.txt

# Starte GUI
cd gui
python main.py
