# Findings & Lessons Learned - Bestell Bot Voice POC

## Audio-Probleme

### 1. Sample-Rate Mismatch (viel Zeit verloren)
**Problem:** Audio war extrem schnell und unverständlich.
**Ursache:** OpenAI Realtime API sendet Audio mit **24kHz**, wir haben es mit 16kHz abgespielt.
**Lösung:** Output-Stream auf 24kHz setzen, Input kann bei 16kHz bleiben (wird vor dem Senden resampled).

```python
# FALSCH: Gleiche Sample-Rate für Input und Output
self._output_stream = sd.OutputStream(samplerate=16000, ...)

# RICHTIG: 24kHz für Output (API liefert 24kHz)
self._output_stream = sd.OutputStream(samplerate=24000, ...)
```

### 2. Audio-Chunk-Größen variabel
**Problem:** API sendet variable Chunk-Größen, Output-Stream erwartet feste Größen.
**Lösung:** Internen Buffer verwenden, der Chunks sammelt und passend ausgibt.

```python
# Chunks sammeln bis genug für einen Frame
self._output_audio_buffer: list[np.ndarray] = []
```

### 3. Gerätauswahl nicht übernommen
**Problem:** LocalAudioDevice nutzte Standard-Gerät statt ausgewähltem.
**Lösung:** Device-IDs explizit an `sd.InputStream/OutputStream` übergeben.

---

## OpenAI Realtime API

### 4. Response muss explizit getriggert werden
**Problem:** Nach Sprach-Ende kam keine AI-Antwort.
**Ursache:** Server-VAD erkennt Sprach-Ende, aber Response wird nicht automatisch generiert.
**Lösung:** NICHT manuell `response.create` senden - die Server-VAD macht das automatisch.

**ABER:** Wenn man `response.create` manuell sendet während bereits eine Response läuft:
```
Error: Conversation already has an active response in progress
```

**Best Practice:** `response_in_progress` Flag tracken, nur senden wenn False.

### 5. Function Calling benötigt spezielle Event-Behandlung
**Events:**
- `response.function_call_arguments.delta` - Argumente werden gestreamt
- `response.function_call_arguments.done` - Argumente komplett, jetzt ausführen
- Nach Ausführung: `conversation.item.create` mit `function_call_output` + `response.create`

### 6. Audio-Callback muss gesetzt sein
**Problem:** Audio wurde empfangen aber nicht abgespielt.
**Ursache:** `set_audio_callback()` wurde nicht aufgerufen oder zu spät.
**Lösung:** Callback in `AudioHandler.start()` setzen, BEVOR `RealtimeClient.connect()`.

---

## Windows-spezifische Probleme

### 7. Unicode/Emoji-Ausgabe in Terminal
**Problem:** `UnicodeEncodeError` bei Emojis in print-Statements.
**Lösung:** 
```python
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
```

### 8. pjsua2 nicht verfügbar auf Windows
**Problem:** SIP-Library pjsua2 ist ein C-Binding, schwer auf Windows zu installieren.
**Lösung:** Optionale Komponente machen, Fallback auf lokales Mikrofon/Lautsprecher.

---

## Qt/PySide6

### 9. Signal-Namen genau beachten
**Problem:** `AttributeError: 'AppSignals' object has no attribute 'transcript_update'`
**Ursache:** Signal hieß `transcript_updated` (mit 'd').
**Lösung:** Signal-Namen immer aus der Definition kopieren, nicht auswendig schreiben.

### 10. UI-Updates nur über Signals
**Problem:** Crashes bei direkten UI-Updates aus anderen Threads.
**Lösung:** Immer Qt Signals verwenden, die automatisch Thread-safe sind.

---

## Katalog/Suche

### 11. Umlaute in Suche
**Problem:** Suche nach "T-Stück" findet "T-Stueck" nicht.
**Lösung:** Normalisierung beider Seiten:
```python
def _normalize_search(text: str) -> str:
    replacements = {"ü": "ue", "ö": "oe", "ä": "ae", ...}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
```

### 12. Kontext-Größe bei vielen Produkten
**Problem:** 375 Produkte = ~20.000 Zeichen im Kontext, teuer und langsam.
**Lösung:** Function Calling nutzen - nur Produkttypen im Kontext, Details on-demand abfragen.

---

## Architektur-Erkenntnisse

### 13. Audio-Flow muss klar sein
```
Mikrofon (16kHz) 
    → AudioBuffer (in) 
    → AudioHandler (resample zu 24kHz) 
    → RealtimeClient 
    → API

API (24kHz) 
    → RealtimeClient 
    → AudioHandler (Callback) 
    → AudioBuffer (out) 
    → Lautsprecher (24kHz)
```

### 14. Session-State zurücksetzen
**Problem:** Bei neuem Anruf war `response_in_progress` noch True vom letzten Anruf.
**Lösung:** `session.reset()` beim Disconnect aufrufen.

### 15. Graceful Shutdown wichtig
Audio-Streams müssen sauber gestoppt werden, sonst Crashes:
```python
def stop(self):
    self._running = False
    if self._input_stream:
        self._input_stream.stop()
        self._input_stream.close()
```

---

## Performance-Tipps

1. **Audio-Buffer klein halten** (15 Frames = ~300ms) für niedrige Latenz
2. **Non-blocking pulls** im Audio-Callback: `timeout=0`
3. **Logging sparsam** im Audio-Hot-Path (nur alle N Frames)
4. **Resampling ist teuer** - wenn möglich Sample-Raten matchen

---

---

## SIP/VoIP-Integration (viel Zeit verloren!)

### 16. PJSIP/pjsua2 auf Windows extrem schwierig
**Problem:** pjsua2 ist ein C++ Binding, braucht:
- Visual Studio C++ Build Tools
- SWIG installiert und im PATH
- Admin-Rechte für bestimmte Schritte
- Manuelle Compilation mit spezifischen Flags

**Lösung:** **pyVoIP** verwenden - pure Python, `pip install pyVoIP` funktioniert sofort.

```python
# Statt pjsua2:
from pyVoIP.VoIPPhone import VoIPPhone

phone = VoIPPhone(
    server=sip_server,
    port=5060,
    username=sip_user,
    password=sip_password,
    callCallback=self._on_incoming_call
)
phone.start()
```

### 17. Python 3.13: audioop Modul entfernt
**Problem:** `ModuleNotFoundError: No module named 'audioop'` - pyVoIP braucht audioop.
**Ursache:** Python 3.13 hat das `audioop` Modul entfernt (deprecated seit 3.11).
**Lösung:** Backport installieren:
```bash
pip install audioop-lts
```

### 18. pyVoIP Callback-Modell verstehen (KRITISCH!)
**Problem:** Auto-Accept funktionierte nicht, App crashte bei Anrufannahme.
**Ursache:** pyVoIP's `callCallback` läuft in einem eigenen Thread. Der Call MUSS direkt im Callback beantwortet werden!

**FALSCH:**
```python
def _on_incoming_call(self, call):
    self.incoming_call.emit(caller_id)  # Emit signal
    # Später in anderem Thread: call.answer() → CRASH!
```

**RICHTIG:**
```python
def _on_incoming_call(self, call):
    self.incoming_call.emit(caller_id)
    if self._auto_accept:
        time.sleep(0.5)  # Kurz warten für Stabilität
        call.answer()    # DIREKT hier im Callback!
        self._handle_call_audio(call)  # Audio-Loop hier starten
```

### 19. G.711 u-law Audio-Dekodierung
**Problem:** Audio an API gesendet aber keine Sprache erkannt.
**Ursache:** pyVoIP liefert **8kHz 8-bit G.711 u-law** (nicht raw PCM!).

**Die Konvertierung muss sein:**
1. G.711 u-law (8kHz 8-bit) → PCM16 (8kHz 16-bit) dekodieren
2. 8kHz → 16kHz resampling
3. An AudioBridge als "L16" (nicht "PCMU"!) übergeben

```python
def _convert_8k_ulaw_to_16k_pcm(self, ulaw_data: bytes) -> bytes:
    """Konvertiert 8kHz u-law zu 16kHz 16-bit PCM."""
    # Schritt 1: u-law dekodieren
    ulaw_table = self._get_ulaw_decode_table()
    samples_8k = np.array([ulaw_table[b] for b in ulaw_data], dtype=np.int16)
    
    # Schritt 2: 8kHz → 16kHz resamplen (Faktor 2)
    samples_16k = np.repeat(samples_8k, 2)  # Einfaches Upsampling
    
    return samples_16k.tobytes()

@staticmethod
def _get_ulaw_decode_table() -> list[int]:
    """G.711 u-law Dekodierungstabelle."""
    table = []
    for i in range(256):
        val = ~i
        sign = (val & 0x80)
        exponent = (val >> 4) & 0x07
        mantissa = val & 0x0F
        sample = (mantissa << 3) + 0x84
        sample <<= (exponent - 1) if exponent > 1 else 0
        sample = -sample if sign else sample
        table.append(sample)
    return table
```

### 20. Codec-Parameter bei AudioBridge
**Problem:** Audio im AudioBridge war beschädigt.
**Ursache:** SIP Client konvertierte bereits zu PCM16, aber AudioBridge versuchte nochmal PCMU zu dekodieren.

**FALSCH:**
```python
# In Controller:
self._audio_bridge.receive_from_sip(pcm_data, codec="PCMU")  # NEIN!
```

**RICHTIG:**
```python
# Wenn SIP Client bereits zu PCM16 konvertiert hat:
self._audio_bridge.receive_from_sip(pcm_data, codec="L16")  # Linear PCM
```

### 21. Sipgate-spezifische Konfiguration
```env
SIP_SERVER=sipconnect.sipgate.de
SIP_USERNAME=<deine sipgate web user-id>  # z.B. 1234567t0
SIP_PASSWORD=<dein sipgate web passwort>
SIP_PORT=5060
```

**Wichtig:** Sipgate versucht Opus-Codec, pyVoIP unterstützt nur PCMU/PCMA:
```
UserWarning: RTP Payload type opus not found.
```
→ Kann ignoriert werden, Fallback auf PCMU funktioniert.

---

## Allgemeine Python/Windows Probleme

### 22. Circular Imports vermeiden
**Problem:** `ImportError: cannot import name 'SIPClient' from partially initialized module`
**Ursache:** `__init__.py` Dateien importieren Module, die sich gegenseitig importieren.

**Lösung:** Keine Klassen in `__init__.py` importieren:
```python
# FALSCH in core/__init__.py:
from .controller import CallController  # Kann Circular Import verursachen

# RICHTIG:
# Leer lassen oder nur __all__ definieren
```

Stattdessen direkt importieren wo gebraucht:
```python
from core.controller import CallController
```

### 23. Port-Konflikte bei Neustart
**Problem:** `[WinError 10048] Socketadresse bereits verwendet`
**Ursache:** Alte Python-Prozesse laufen noch im Hintergrund.

**Lösung vor jedem Start:**
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
python main.py
```

### 24. PowerShell Syntax-Unterschiede
**Problem:** Bash-Befehle funktionieren nicht in PowerShell.
- `&&` → `;` (oder separate Befehle)
- Heredoc `<<'EOF'` → nicht verfügbar, einfache Strings nutzen
- `export VAR=value` → `$env:VAR = "value"`

---

## Checkliste für Produktion

- [ ] Sample-Raten konsistent (Input 16kHz, Output 24kHz für OpenAI)
- [ ] Audio-Callbacks vor connect() setzen
- [ ] Session-State bei Disconnect zurücksetzen
- [ ] `response_in_progress` Flag tracken
- [ ] Unicode-Encoding für Windows
- [ ] Graceful Shutdown für alle Streams
- [ ] Umlaute in Suche normalisieren
- [ ] Function Calling für große Datensätze
- [ ] **pyVoIP statt pjsua2 für Windows-Kompatibilität**
- [ ] **audioop-lts für Python 3.13+**
- [ ] **G.711 u-law korrekt dekodieren (nicht als raw PCM behandeln!)**
- [ ] **call.answer() DIREKT im pyVoIP Callback**
- [ ] **Codec-Parameter "L16" wenn Audio bereits konvertiert**
- [ ] **Alte Python-Prozesse vor Neustart beenden**
