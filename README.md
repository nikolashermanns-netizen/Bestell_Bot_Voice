# Bestell Bot Voice - POC

Ein Voice-Bot Proof of Concept mit SIP-Integration (Aircall) und ChatGPT Realtime API für Live-Telefon-Bestellungen.

## Features

- **SIP/RTP Integration**: Eingehende Anrufe annehmen/ablehnen/auflegen
- **ChatGPT Realtime API**: Bidirektionales Audio-Streaming
- **Live-Transkription**: Caller und Assistant Text in Echtzeit
- **Turn-Handling**: AI unterbricht wenn Caller spricht
- **Qt6 UI**: Moderne Benutzeroberfläche mit PySide6

## Projektstruktur

```
bestell_bot_voice/
├── main.py              # Einstiegspunkt
├── config.py            # Konfigurationsloader
├── .env.example         # Template für Secrets
├── requirements.txt     # Dependencies
│
├── core/                # Shared Utilities
│   ├── state.py         # CallState, AppState
│   ├── audio_buffer.py  # Thread-safe Ringbuffer
│   ├── signals.py       # Qt Signals
│   └── controller.py    # Zentrale Orchestrierung
│
├── sip/                 # SIP/RTP Handling
│   ├── client.py        # SIP-Registrierung, Call Control
│   ├── audio_bridge.py  # Codec-Konvertierung
│   └── events.py        # Event-Typen
│
├── realtime_ai/         # ChatGPT Streaming
│   ├── client.py        # WebSocket Client
│   ├── audio_handler.py # Audio senden/empfangen
│   └── vad.py           # Voice Activity Detection
│
├── transcription/       # Transkription
│   └── manager.py       # Transkript-Verwaltung
│
└── ui/                  # Qt UI
    ├── main_window.py   # Haupt-UI
    ├── call_panel.py    # Call Controls
    ├── transcript_panel.py
    └── debug_panel.py
```

## Installation

### 1. Repository klonen

```bash
git clone <repo-url>
cd bestell-bot-voice
```

### 2. Virtual Environment erstellen

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# oder
source venv/bin/activate  # Linux/Mac
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 4. Konfiguration

```bash
# .env Datei erstellen
copy .env.example .env

# .env bearbeiten und Credentials eintragen:
# - SIP_SERVER, SIP_USERNAME, SIP_PASSWORD
# - OPENAI_API_KEY
```

### 5. pjsua2 (Optional, für echte SIP-Verbindung)

pjsua2 muss separat installiert werden:

**Windows:**
- PJSIP herunterladen: https://www.pjsip.org/download.htm
- Mit Visual Studio kompilieren
- Python Bindings generieren

**Linux:**
```bash
sudo apt install python3-pjsua
```

Ohne pjsua2 läuft die App im Mock-Modus für Entwicklung.

## Starten

```bash
python main.py
```

## Tests

```bash
# Komponenten-Tests
python test_app.py

# UI Demo (ohne echte Verbindung)
python ui/main_window.py
```

## Architektur

```
                    ┌─────────────────┐
                    │   Qt MainWindow │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  CallController │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌────────▼────────┐   ┌───────▼───────┐
│   SIPClient   │   │  RealtimeClient │   │ TranscriptMgr │
└───────┬───────┘   └────────┬────────┘   └───────────────┘
        │                    │
┌───────▼───────┐   ┌────────▼────────┐
│  AudioBridge  │   │  AudioHandler   │
└───────┬───────┘   └────────┬────────┘
        │                    │
        └────────┬───────────┘
                 │
        ┌────────▼────────┐
        │  Audio Buffers  │
        │  (in/out)       │
        └─────────────────┘
```

## Audio-Flow

```
Caller ─> SIP/RTP ─> AudioBridge ─> audio_in_buffer ─> AudioHandler ─> Realtime API
   ^                                                                        │
   │                                                                        v
   └─── SIP/RTP <── AudioBridge <── audio_out_buffer <── AudioHandler <─────┘
```

## Konfiguration

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| SIP_SERVER | SIP Server Adresse | - |
| SIP_USERNAME | SIP Benutzername | - |
| SIP_PASSWORD | SIP Passwort | - |
| SIP_PORT | SIP Port | 5060 |
| OPENAI_API_KEY | OpenAI API Key | - |
| OPENAI_MODEL | Realtime Model | gpt-4o-realtime-preview-2024-12-17 |
| AUDIO_SAMPLE_RATE | Audio Sample Rate | 16000 |
| LOG_LEVEL | Logging Level | INFO |

## Definition of Done (POC)

- [x] Eingehender Call kann angenommen werden
- [x] Anrufer spricht → ChatGPT antwortet hörbar
- [x] Live-Transkript zeigt Caller + Assistant Text
- [x] App crasht nicht beim Auflegen / erneuten Anruf
- [x] Mute AI stoppt Ausgabe sofort
- [x] Keine UI-Freezes während Audio läuft

## Bekannte Einschränkungen (POC)

- Nur 1 gleichzeitiger Anruf
- Keine Datenbank / Persistenz
- Keine Call Recording
- pjsua2 muss manuell installiert werden

## Lizenz

MIT
