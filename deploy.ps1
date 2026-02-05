# Bestell Bot Voice - Deployment Script
# 
# Dieses Script:
# 1. Commited und pusht lokale Änderungen zu GitHub
# 2. Pullt die Änderungen auf dem Server
# 3. Baut und startet den Docker Container neu
#
# Verwendung:
#   .\deploy.ps1                    # Nur deployen (ohne Commit)
#   .\deploy.ps1 -Message "feat: Beschreibung"  # Mit Commit
#   .\deploy.ps1 -SkipBuild         # Nur Code aktualisieren, kein Docker Rebuild

param(
    [string]$Message = "",
    [switch]$SkipBuild = $false,
    [switch]$Help = $false
)

if ($Help) {
    Write-Host @"
Bestell Bot Voice - Deployment Script

Verwendung:
  .\deploy.ps1                              Nur deployen (ohne Commit)
  .\deploy.ps1 -Message "feat: ..."         Mit Commit
  .\deploy.ps1 -SkipBuild                   Nur Code updaten, kein Docker Build

Optionen:
  -Message <string>   Commit-Message (wenn leer, wird kein Commit gemacht)
  -SkipBuild          Überspringt Docker Build (nur git pull auf Server)
  -Help               Diese Hilfe anzeigen
"@
    exit 0
}

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Bestell Bot Voice - Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Server Pfade
$SERVER_PATH = "/home/nikolas/bestell-bot-voice"
$DOCKER_NAME = "bestell-bot-voice"
$DOCKER_IMAGE = "server_bestell-bot"

# 1. Git Commit und Push (wenn Message angegeben)
if ($Message -ne "") {
    Write-Host "[1/4] Git: Änderungen committen und pushen..." -ForegroundColor Yellow
    
    # Alle Änderungen stagen
    git add -A
    if ($LASTEXITCODE -ne 0) { throw "Git add fehlgeschlagen" }
    
    # Status prüfen
    $status = git status --porcelain
    if ($status) {
        git commit -m $Message
        if ($LASTEXITCODE -ne 0) { throw "Git commit fehlgeschlagen" }
        Write-Host "  Commit erstellt: $Message" -ForegroundColor Green
    } else {
        Write-Host "  Keine Änderungen zum Committen" -ForegroundColor Gray
    }
    
    # Push
    git push origin master
    if ($LASTEXITCODE -ne 0) { throw "Git push fehlgeschlagen" }
    Write-Host "  Push erfolgreich" -ForegroundColor Green
} else {
    Write-Host "[1/4] Git: Kein Commit (keine Message angegeben)" -ForegroundColor Gray
    
    # Prüfen ob lokale Änderungen vorhanden sind die nicht gepusht wurden
    $unpushed = git log origin/master..HEAD --oneline
    if ($unpushed) {
        Write-Host "  Unpushed commits gefunden, pushe..." -ForegroundColor Yellow
        git push origin master
        if ($LASTEXITCODE -ne 0) { throw "Git push fehlgeschlagen" }
    }
}
Write-Host ""

# 2. Auf Server pullen
Write-Host "[2/4] Server: Code aktualisieren..." -ForegroundColor Yellow
$pullCmd = "cd $SERVER_PATH && git checkout -- . && git reset --hard origin/master && git pull origin master"
ssh bot $pullCmd
if ($LASTEXITCODE -ne 0) { throw "Git pull auf Server fehlgeschlagen" }
Write-Host "  Code aktualisiert" -ForegroundColor Green
Write-Host ""

# 3. Docker Container neu bauen und starten
if (-not $SkipBuild) {
    Write-Host "[3/4] Docker: Container neu bauen..." -ForegroundColor Yellow
    $buildCmd = @"
cd $SERVER_PATH/server && \
docker stop $DOCKER_NAME 2>/dev/null; \
docker rm $DOCKER_NAME 2>/dev/null; \
docker build -t $DOCKER_IMAGE . && \
docker run -d \
    --name $DOCKER_NAME \
    --network host \
    --env-file .env \
    -v $SERVER_PATH/server/config:/app/config \
    -v $SERVER_PATH/server/system_katalog:/app/system_katalog \
    $DOCKER_IMAGE
"@
    ssh bot $buildCmd
    if ($LASTEXITCODE -ne 0) { throw "Docker build/run fehlgeschlagen" }
    Write-Host "  Container gestartet" -ForegroundColor Green
} else {
    Write-Host "[3/4] Docker: Build übersprungen (-SkipBuild)" -ForegroundColor Gray
}
Write-Host ""

# 4. Status prüfen
Write-Host "[4/4] Status prüfen..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

$statusCmd = "docker logs --tail 10 $DOCKER_NAME 2>&1 | grep -E 'Registration|registriert|ERROR|running'"
$logs = ssh bot $statusCmd

Write-Host "  Container Logs:" -ForegroundColor Cyan
Write-Host $logs

# Health Check
$healthCmd = "curl -s http://localhost:8085/status 2>/dev/null | head -c 200"
$health = ssh bot $healthCmd
if ($health) {
    Write-Host ""
    Write-Host "  API Status: OK" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  API Status: Nicht erreichbar (Container startet noch?)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
