#!/bin/bash
# Update Server - Git Commit und Deploy
# ======================================

set -e  # Bei Fehler abbrechen

# Konfiguration
SERVER_USER="root"
SERVER_HOST="10.200.200.1"
SERVER_PATH="/root/bestell-bot"

echo "=== Bestell Bot Voice - Server Update ==="
echo ""

# 1. Git Status anzeigen
echo "[1/4] Git Status:"
git status --short
echo ""

# 2. Commit erstellen
read -p "Commit-Nachricht eingeben: " COMMIT_MSG

if [ -z "$COMMIT_MSG" ]; then
    echo "Keine Commit-Nachricht eingegeben. Abbruch."
    exit 1
fi

echo "[2/4] Änderungen committen..."
git add -A
git commit -m "$COMMIT_MSG"
echo ""

# 3. Zum Server pushen (falls Remote existiert)
echo "[3/4] Push zu Remote..."
git push origin master || echo "Push fehlgeschlagen oder kein Remote - fahre fort"
echo ""

# 4. Auf Server deployen
echo "[4/4] Deploy auf Server ($SERVER_HOST)..."
ssh ${SERVER_USER}@${SERVER_HOST} << 'ENDSSH'
    cd /root/bestell-bot/server
    git pull
    docker-compose down
    docker-compose up -d --build
    echo "Server neu gestartet!"
ENDSSH

echo ""
echo "=== Update abgeschlossen ==="
