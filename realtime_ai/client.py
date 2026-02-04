"""
OpenAI Realtime API Client für Streaming Audio und Text.

Verwendet WebSocket-Verbindung zur OpenAI Realtime API für:
- Audio-Streaming (bidirektional)
- Live-Transkription
- Voice Activity Detection (VAD)
- Turn-Handling
"""

import asyncio
import json
import base64
import logging
import threading
from typing import Callable, Optional
from dataclasses import dataclass, field
import websockets
from websockets.client import WebSocketClientProtocol

from config import OpenAIConfig, AudioConfig
from core.signals import AppSignals

logger = logging.getLogger(__name__)


@dataclass
class RealtimeSession:
    """Session-Informationen für die Realtime API."""

    session_id: str = ""
    model: str = ""
    voice: str = "alloy"
    is_connected: bool = False
    is_speaking: bool = False
    response_in_progress: bool = False
    
    def reset(self) -> None:
        """Setzt Session-Status zurück."""
        self.session_id = ""
        self.is_connected = False
        self.is_speaking = False
        self.response_in_progress = False


@dataclass
class RealtimeConfig:
    """Konfiguration für die Realtime Session."""

    voice: str = "alloy"
    turn_detection: dict = field(default_factory=lambda: {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
    })
    instructions: str = """Du bist ein erfahrener SHK-Fachberater und Viega-Experte bei einem Fachgroßhandel.

DEINE ROLLE:
- Du nimmst telefonische Bestellungen von SHK-Profis (Installateure, Heizungsbauer) entgegen
- Du kennst das komplette Viega-Sortiment (Profipress, Temponox, Sanpress, Megapress, etc.)
- Du hilfst bei der Produktauswahl und gibst technische Beratung

WICHTIGE REGELN:
- Sprich immer auf Deutsch
- Halte deine Antworten kurz und professionell
- Frage nach Menge und Größe wenn nicht angegeben
- Wiederhole die Bestellung zur Bestätigung
- Nenne immer die Artikelnummer (Kennung) mit

BESTELLFORMAT:
Wenn der Kunde etwas bestellt, bestätige so:
"[MENGE]x [PRODUKTNAME] (Art.Nr: [KENNUNG]) - notiert!"

Beispiel: "10x Profipress Bogen 90° 22mm (Art.Nr: 294540) - notiert!"

Begrüße den Anrufer freundlich und frage wie du helfen kannst."""
    
    tools: list = field(default_factory=list)


# Standard-Tools für Produktsuche
PRODUCT_SEARCH_TOOL = {
    "type": "function",
    "name": "suche_produkt",
    "description": "Sucht Viega-Produkte in der Datenbank nach Produkttyp und optional Größe. Nutze diese Funktion um die exakte Artikelnummer zu finden.",
    "parameters": {
        "type": "object",
        "properties": {
            "produkttyp": {
                "type": "string",
                "description": "Der Produkttyp, z.B. 'Bogen 90°', 'Muffe', 'T-Stück', 'Doppelnippel', 'Kappe', 'Rohr'"
            },
            "groesse": {
                "type": "string",
                "description": "Die Größe in mm, z.B. '15mm', '22mm', '28mm'. Optional."
            },
            "system": {
                "type": "string",
                "description": "Das System/Werkstoff, z.B. 'TEMPONOX', 'INOX', 'ROTGUSS'. Optional."
            }
        },
        "required": ["produkttyp"]
    }
}


class RealtimeClient:
    """
    Client für die OpenAI Realtime API.

    Verbindet sich über WebSocket und ermöglicht:
    - Audio-Streaming zum Modell
    - Audio-Antworten empfangen
    - Live-Transkription
    - VAD-basiertes Turn-Handling
    - Automatische Reconnection
    """

    # API Endpoint
    REALTIME_URL = "wss://api.openai.com/v1/realtime"

    # Reconnect-Konfiguration
    RECONNECT_DELAY_INITIAL = 1.0
    RECONNECT_DELAY_MAX = 30.0
    RECONNECT_DELAY_MULTIPLIER = 2.0
    MAX_RECONNECT_ATTEMPTS = 5

    def __init__(
        self,
        openai_config: OpenAIConfig,
        audio_config: AudioConfig,
        signals: AppSignals,
    ):
        """
        Initialisiert den Realtime Client.

        Args:
            openai_config: OpenAI API Konfiguration
            audio_config: Audio-Einstellungen
            signals: Qt Signals für UI-Updates
        """
        self._openai_config = openai_config
        self._audio_config = audio_config
        self._signals = signals

        self._session = RealtimeSession()
        self._config = RealtimeConfig()

        self._ws: Optional[WebSocketClientProtocol] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        self._running = False
        self._should_reconnect = True
        self._reconnect_delay = self.RECONNECT_DELAY_INITIAL
        self._reconnect_attempts = 0

        # Callbacks
        self._on_audio: Optional[Callable[[bytes], None]] = None
        self._on_transcript: Optional[Callable[[str, str, bool], None]] = None
        self._on_function_call: Optional[Callable[[str, str], str]] = None

    def connect(self) -> None:
        """Startet die WebSocket-Verbindung in einem separaten Thread."""
        if self._running:
            logger.warning("RealtimeClient läuft bereits")
            return

        self._running = True

        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="RealtimeClient",
            daemon=True,
        )
        self._thread.start()

    def _run_event_loop(self) -> None:
        """Führt den asyncio Event Loop im Thread aus."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._connect_and_run())
        except Exception as e:
            logger.error(f"Realtime Event Loop Fehler: {e}")
            self._signals.error_occurred.emit(str(e))
        finally:
            self._loop.close()

    async def _connect_and_run(self) -> None:
        """Verbindet und verarbeitet Messages."""
        url = f"{self.REALTIME_URL}?model={self._openai_config.model}"

        headers = {
            "Authorization": f"Bearer {self._openai_config.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        try:
            async with websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10,
            ) as ws:
                self._ws = ws
                self._session.is_connected = True
                self._signals.ai_connection_changed.emit(True)
                logger.info("Realtime API verbunden")

                # Session konfigurieren
                await self._configure_session()

                # Message Loop
                await self._message_loop()

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Realtime Verbindung geschlossen: {e}")
            await self._handle_disconnect()
        except Exception as e:
            logger.error(f"Realtime Verbindungsfehler: {e}")
            self._signals.error_occurred.emit(f"AI Verbindungsfehler: {e}")
            await self._handle_disconnect()
        finally:
            self._session.is_connected = False
            self._signals.ai_connection_changed.emit(False)

    async def _handle_disconnect(self) -> None:
        """Behandelt Verbindungsverlust und plant Reconnect."""
        if not self._should_reconnect or not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max Reconnect-Versuche erreicht")
            self._signals.error_occurred.emit("AI: Maximale Reconnect-Versuche erreicht")
            return

        logger.info(
            f"Reconnect in {self._reconnect_delay:.1f}s "
            f"(Versuch {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})"
        )

        await asyncio.sleep(self._reconnect_delay)

        # Exponential backoff
        self._reconnect_delay = min(
            self._reconnect_delay * self.RECONNECT_DELAY_MULTIPLIER,
            self.RECONNECT_DELAY_MAX,
        )

        if self._running and self._should_reconnect:
            await self._connect_and_run()

    async def _configure_session(self) -> None:
        """Konfiguriert die Realtime Session."""
        session_config = {
            "modalities": ["text", "audio"],
            "voice": self._config.voice,
            "instructions": self._config.instructions,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "whisper-1",
            },
            "turn_detection": self._config.turn_detection,
        }
        
        # Tools hinzufügen wenn vorhanden
        if self._config.tools:
            session_config["tools"] = self._config.tools
            session_config["tool_choice"] = "auto"
        
        config_event = {
            "type": "session.update",
            "session": session_config,
        }

        await self._send_event(config_event)
        logger.info("Realtime Session konfiguriert")

    async def _message_loop(self) -> None:
        """Verarbeitet eingehende WebSocket-Nachrichten."""
        while self._running and self._ws:
            try:
                message = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=1.0,
                )

                event = json.loads(message)
                await self._handle_event(event)

            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Message Loop Fehler: {e}")

    async def _handle_event(self, event: dict) -> None:
        """
        Verarbeitet ein Realtime API Event.

        Wichtige Events:
        - session.created: Session wurde erstellt
        - response.audio.delta: Audio-Chunk
        - response.audio_transcript.delta: Text der Antwort
        - input_audio_buffer.speech_started: Caller spricht
        - input_audio_buffer.speech_stopped: Caller fertig
        - conversation.item.input_audio_transcription.completed: Caller Text
        """
        event_type = event.get("type", "")

        if event_type == "session.created":
            self._session.session_id = event.get("session", {}).get("id", "")
            logger.info(f"Session erstellt: {self._session.session_id}")

        elif event_type == "session.updated":
            logger.debug("Session aktualisiert")
            # Reconnect-Counter zurücksetzen bei erfolgreicher Session
            self._reconnect_attempts = 0
            self._reconnect_delay = self.RECONNECT_DELAY_INITIAL

        elif event_type == "response.audio.delta":
            # Audio-Chunk empfangen
            audio_b64 = event.get("delta", "")
            if audio_b64:
                audio_data = base64.b64decode(audio_b64)
                if self._on_audio:
                    self._on_audio(audio_data)
                else:
                    logger.warning("Audio empfangen aber kein Callback gesetzt!")

        elif event_type == "response.audio_transcript.delta":
            # Assistant Transkript (partial)
            text = event.get("delta", "")
            if text:
                self._emit_transcript("assistant", text, is_final=False)

        elif event_type == "response.audio_transcript.done":
            # Assistant Transkript (final)
            transcript = event.get("transcript", "")
            if transcript:
                self._emit_transcript("assistant", transcript, is_final=True)

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Caller Transkript (final)
            transcript = event.get("transcript", "")
            if transcript:
                self._emit_transcript("caller", transcript, is_final=True)

        elif event_type == "input_audio_buffer.speech_started":
            # Caller fängt an zu sprechen
            self._session.is_speaking = True
            logger.debug("Caller spricht...")

        elif event_type == "input_audio_buffer.speech_stopped":
            # Caller hat aufgehört zu sprechen
            self._session.is_speaking = False
            logger.debug("Caller fertig")
            # Response wird automatisch durch Server-VAD getriggert
            # Kein manuelles response.create nötig

        elif event_type == "response.created":
            self._session.response_in_progress = True
            logger.debug("Antwort wird generiert...")

        elif event_type == "response.done":
            self._session.response_in_progress = False
            logger.debug("Antwort abgeschlossen")

        elif event_type == "response.function_call_arguments.done":
            # Function Call abgeschlossen - Argumente auswerten
            call_id = event.get("call_id", "")
            name = event.get("name", "")
            arguments = event.get("arguments", "{}")
            
            logger.info(f"Function Call: {name}({arguments})")
            
            # Callback aufrufen falls gesetzt
            if self._on_function_call:
                try:
                    result = self._on_function_call(name, arguments)
                    # Ergebnis zurück an API senden
                    await self._send_function_result(call_id, result)
                except Exception as e:
                    logger.error(f"Function Call Fehler: {e}")
                    await self._send_function_result(call_id, f"Fehler: {e}")

        elif event_type == "error":
            error = event.get("error", {})
            error_msg = error.get("message", "Unbekannter Fehler")
            logger.error(f"Realtime API Fehler: {error_msg}")
            self._signals.error_occurred.emit(f"AI: {error_msg}")

        elif event_type == "input_audio_buffer.committed":
            logger.info("Audio Buffer committed")
            
        elif event_type == "conversation.item.created":
            item_type = event.get("item", {}).get("type", "")
            logger.info(f"Conversation Item erstellt: {item_type}")

        else:
            # Alle Events loggen für Debug
            logger.info(f"API Event: {event_type}")

    def _emit_transcript(self, speaker: str, text: str, is_final: bool) -> None:
        """Emittiert Transkript-Update."""
        self._signals.transcript_updated.emit(speaker, text, is_final)

        if self._on_transcript:
            self._on_transcript(speaker, text, is_final)

    async def _send_event(self, event: dict) -> None:
        """Sendet ein Event an die Realtime API."""
        if self._ws:
            await self._ws.send(json.dumps(event))

    def send_audio(self, pcm_data: bytes) -> None:
        """
        Sendet Audio-Daten an die Realtime API.

        Args:
            pcm_data: 16-bit PCM Audio @ 24kHz
        """
        if not self._running or not self._loop:
            return

        # Base64 encodieren
        audio_b64 = base64.b64encode(pcm_data).decode("utf-8")

        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }

        # Thread-safe in Event Loop einreihen
        asyncio.run_coroutine_threadsafe(
            self._send_event(event),
            self._loop,
        )

    def cancel_response(self) -> None:
        """Bricht die aktuelle Antwort ab (für Interruption)."""
        if not self._running or not self._loop:
            return

        if not self._session.response_in_progress:
            return  # Nichts abzubrechen

        event = {"type": "response.cancel"}

        asyncio.run_coroutine_threadsafe(
            self._send_event(event),
            self._loop,
        )

        self._session.response_in_progress = False
        logger.debug("Antwort abgebrochen")

    def clear_audio_buffer(self) -> None:
        """Leert den Input-Audio-Buffer."""
        if not self._running or not self._loop:
            return

        event = {"type": "input_audio_buffer.clear"}

        asyncio.run_coroutine_threadsafe(
            self._send_event(event),
            self._loop,
        )

    def commit_audio(self) -> None:
        """
        Commited den Audio-Buffer und triggert eine Antwort.

        Normalerweise wird dies automatisch durch VAD getriggert.
        """
        if not self._running or not self._loop:
            return

        event = {"type": "input_audio_buffer.commit"}

        asyncio.run_coroutine_threadsafe(
            self._send_event(event),
            self._loop,
        )

    def create_response(self) -> None:
        """
        Fordert explizit eine Antwort von der API an.
        
        Wird aufgerufen nachdem Sprache beendet wurde.
        """
        if not self._running or not self._loop:
            return

        event = {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
            }
        }

        asyncio.run_coroutine_threadsafe(
            self._send_event(event),
            self._loop,
        )
        logger.debug("Response angefordert")

    def set_audio_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Setzt Callback für empfangene Audio-Daten.

        Args:
            callback: Funktion die mit PCM-Daten aufgerufen wird
        """
        self._on_audio = callback

    def set_transcript_callback(
        self, callback: Callable[[str, str, bool], None]
    ) -> None:
        """
        Setzt Callback für Transkript-Updates.

        Args:
            callback: Funktion(speaker, text, is_final)
        """
        self._on_transcript = callback

    def set_function_call_callback(
        self, callback: Callable[[str, str], str]
    ) -> None:
        """
        Setzt Callback für Function Calls.

        Args:
            callback: Funktion(function_name, arguments_json) -> result_string
        """
        self._on_function_call = callback

    def set_tools(self, tools: list) -> None:
        """Setzt die verfügbaren Tools/Functions."""
        self._config.tools = tools
        
        # Wenn verbunden, Session updaten
        if self._running and self._loop:
            session_update = {
                "tools": tools,
                "tool_choice": "auto" if tools else "none",
            }
            event = {
                "type": "session.update",
                "session": session_update,
            }
            asyncio.run_coroutine_threadsafe(
                self._send_event(event),
                self._loop,
            )

    async def _send_function_result(self, call_id: str, result: str) -> None:
        """Sendet das Ergebnis eines Function Calls zurück an die API."""
        # Conversation item für das Ergebnis erstellen
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        }
        await self._send_event(event)
        
        # Response anfordern damit AI weitermacht
        await self._send_event({
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
            }
        })
        logger.debug(f"Function result gesendet: {result[:100]}...")

    def set_instructions(self, instructions: str) -> None:
        """Setzt die System-Anweisungen für den Assistenten."""
        self._config.instructions = instructions

        # Wenn verbunden, Session updaten
        if self._running and self._loop:
            event = {
                "type": "session.update",
                "session": {
                    "instructions": instructions,
                },
            }
            asyncio.run_coroutine_threadsafe(
                self._send_event(event),
                self._loop,
            )

    def set_model(self, model: str) -> None:
        """
        Setzt das AI-Model.
        
        HINWEIS: Das Model kann nur geändert werden wenn NICHT verbunden.
        Bei aktiver Verbindung muss erst disconnect() und dann connect() 
        aufgerufen werden.
        
        Args:
            model: Model-Name (z.B. "gpt-4o-realtime-preview-2024-12-17" oder "gpt-realtime")
        """
        self._openai_config.model = model
        self._session.model = model
        logger.info(f"AI-Model gesetzt: {model}")

    def get_model(self) -> str:
        """Gibt das aktuelle Model zurück."""
        return self._openai_config.model

    def disconnect(self) -> None:
        """Trennt die WebSocket-Verbindung."""
        self._running = False
        self._should_reconnect = False

        if self._ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._ws.close(),
                    self._loop,
                )
            except Exception as e:
                logger.warning(f"Fehler beim Schließen: {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        # Session komplett zurücksetzen
        self._session.reset()
        self._signals.ai_connection_changed.emit(False)
        logger.info("Realtime Client getrennt")

    @property
    def is_connected(self) -> bool:
        """Gibt zurück ob verbunden."""
        return self._session.is_connected

    @property
    def is_speaking(self) -> bool:
        """Gibt zurück ob Caller gerade spricht."""
        return self._session.is_speaking


# Demo/Test
if __name__ == "__main__":
    import sys
    import time
    from PySide6.QtWidgets import QApplication
    from core.signals import init_signals
    import numpy as np

    app = QApplication(sys.argv)
    signals = init_signals()

    # Benötigt echten API Key
    import os
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        print("OPENAI_API_KEY nicht gesetzt!")
        sys.exit(1)

    openai_config = OpenAIConfig(api_key=api_key)
    audio_config = AudioConfig()

    client = RealtimeClient(openai_config, audio_config, signals)

    # Callbacks
    def on_audio(data: bytes):
        print(f"Audio empfangen: {len(data)} bytes")

    def on_connection(connected: bool):
        print(f"Verbindung: {'Ja' if connected else 'Nein'}")

    def on_transcript(speaker: str, text: str, is_final: bool):
        marker = "[FINAL]" if is_final else "[...]"
        print(f"{marker} {speaker}: {text}")

    client.set_audio_callback(on_audio)
    signals.ai_connection_changed.connect(on_connection)
    signals.transcript_updated.connect(on_transcript)

    # Verbinden
    print("Verbinde mit Realtime API...")
    client.connect()

    # Warte auf Verbindung
    time.sleep(3)

    # Test-Audio senden (Stille)
    print("Sende Test-Audio...")
    silence = bytes(3200)  # 100ms @ 16kHz
    client.send_audio(silence)

    # Warte und cleanup
    time.sleep(5)
    client.disconnect()

    print("Test abgeschlossen")
