#!/bin/bash
# Update Server - Git Commit und Deploy
# ======================================

set -e  # Bei Fehler abbrechen

# Konfiguration
# WICHTIG: SSH-Alias "bot" verwenden - direkter Zugriff auf Port 22 ist blockiert!
SSH_ALIAS="bot"
SERVER_PATH="/home/nikolas/bestell-bot-voice"

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
echo "[4/4] Deploy auf Server (via SSH-Alias: $SSH_ALIAS)..."
ssh $SSH_ALIAS "cd $SERVER_PATH && git pull origin master"

echo ""
echo "[5/7] Docker Container neu starten..."
ssh $SSH_ALIAS "docker stop bestell-bot-voice; docker rm bestell-bot-voice; cd $SERVER_PATH/server && docker build -t server_bestell-bot . && docker run -d --name bestell-bot-voice --network host --env-file .env -v $SERVER_PATH/server/config:/app/config -v $SERVER_PATH/server/system_katalog:/app/system_katalog -v $SERVER_PATH/server/wissen:/app/wissen server_bestell-bot"

echo ""
echo "[6/7] Python-Code in Container kopieren (fuer Live-Updates)..."
ssh $SSH_ALIAS "docker cp $SERVER_PATH/server/app/. bestell-bot-voice:/app/app/"
ssh $SSH_ALIAS "docker cp $SERVER_PATH/server/main.py bestell-bot-voice:/app/main.py"

echo ""
echo "[7/7] Status prüfen..."
sleep 3
ssh $SSH_ALIAS "docker logs --tail 20 bestell-bot-voice"

echo ""
echo "=== Update abgeschlossen ==="
