"""
OpenAI Realtime API Client für Voice Bot.

Streamt Audio bidirektional zur OpenAI API via WebSocket.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTIONS = """Du bist ein freundlicher Bestellassistent für einen Sanitär-Großhandel.
                
Deine Aufgaben:
- Begrüße Anrufer freundlich
- Nimm Bestellungen entgegen
- Frage nach Produktnamen, Artikelnummern und Mengen
- Bestätige die Bestellung am Ende

Sprich kurz und präzise. Vermeide lange Erklärungen."""


# Verfügbare OpenAI Realtime Modelle
AVAILABLE_MODELS = [
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-mini-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview",
]

DEFAULT_MODEL = "gpt-4o-realtime-preview-2024-12-17"


class AIClient:
    """
    Async Client für OpenAI Realtime API via WebSocket.
    """
    
    # Audio Formate
    INPUT_SAMPLE_RATE = 16000   # AI erwartet 16kHz
    OUTPUT_SAMPLE_RATE = 24000  # AI sendet 24kHz
    
    REALTIME_BASE_URL = "wss://api.openai.com/v1/realtime?model="
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self._ws = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        
        self.muted = False
        self.instructions = DEFAULT_INSTRUCTIONS
        self._model = model if model in AVAILABLE_MODELS else DEFAULT_MODEL
        
        # Event Callbacks
        self.on_audio_response: Optional[Callable[[bytes], None]] = None
        self.on_transcript: Optional[Callable[[str, str, bool], None]] = None
    
    @property
    def model(self) -> str:
        """Aktuelles Modell."""
        return self._model
    
    def set_model(self, model: str) -> bool:
        """Setzt das Modell (wird beim nächsten Anruf aktiv)."""
        if model in AVAILABLE_MODELS:
            self._model = model
            logger.info(f"Modell geändert zu: {model}")
            return True
        logger.warning(f"Unbekanntes Modell: {model}")
        return False
    
    def get_realtime_url(self) -> str:
        """Generiert die Realtime API URL mit aktuellem Modell."""
        return f"{self.REALTIME_BASE_URL}{self._model}"
    
    @property
    def is_connected(self) -> bool:
        """Ist die WebSocket-Verbindung aktiv?"""
        return self._ws is not None and self._running
    
    async def connect(self):
        """Verbindung zur Realtime API aufbauen."""
        try:
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            realtime_url = self.get_realtime_url()
            logger.info(f"Verbinde zu OpenAI mit Modell: {self._model}")
            
            session = aiohttp.ClientSession()
            self._ws = await session.ws_connect(
                realtime_url,
                headers=headers
            )
            self._session = session
            self._running = True
            
            # Session konfigurieren
            await self._configure_session()
            
            # Receive Loop starten
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info("OpenAI Realtime API verbunden")
            
        except Exception as e:
            logger.error(f"OpenAI Verbindung fehlgeschlagen: {e}")
            self._running = False
    
    async def _configure_session(self):
        """Session mit Instruktionen konfigurieren."""
        if not self._ws:
            return
        
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                }
            }
        }
        
        await self._ws.send_str(json.dumps(config))
        logger.info("Session konfiguriert")
    
    async def _receive_loop(self):
        """Empfängt Events von der Realtime API."""
        if not self._ws:
            return
        
        try:
            async for msg in self._ws:
                if not self._running:
                    break
                
                if msg.type == 1:  # TEXT
                    try:
                        event = json.loads(msg.data)
                        await self._handle_event(event)
                    except json.JSONDecodeError:
                        logger.warning("Ungültiges JSON von API")
                elif msg.type == 258:  # CLOSED
                    break
                elif msg.type == 256:  # ERROR
                    logger.error(f"WebSocket Fehler: {msg.data}")
                    break
                    
        except Exception as e:
            logger.error(f"Receive Loop Fehler: {e}")
        finally:
            self._running = False
    
    async def _handle_event(self, event: dict):
        """Verarbeitet ein Event von der API."""
        event_type = event.get("type", "")
        
        # Log alle Events (außer audio.delta wegen Menge)
        if event_type not in ["response.audio.delta", "input_audio_buffer.speech_started", 
                               "input_audio_buffer.speech_stopped", "input_audio_buffer.committed"]:
            logger.info(f"[OpenAI Event] {event_type}")
        
        if event_type == "response.audio.delta":
            # Audio-Chunk empfangen
            audio_b64 = event.get("delta", "")
            if audio_b64 and not self.muted:
                audio_bytes = base64.b64decode(audio_b64)
                
                # Log erstes Audio-Chunk
                if not hasattr(self, '_audio_chunk_count'):
                    self._audio_chunk_count = 0
                self._audio_chunk_count += 1
                if self._audio_chunk_count == 1:
                    logger.info(f"[OpenAI] Erstes Audio-Chunk empfangen, size={len(audio_bytes)}")
                
                if self.on_audio_response:
                    await self.on_audio_response(audio_bytes)
        
        elif event_type == "input_audio_buffer.speech_started":
            logger.info("[OpenAI] Sprache erkannt - VAD gestartet")
        
        elif event_type == "input_audio_buffer.speech_stopped":
            logger.info("[OpenAI] Sprache beendet - VAD gestoppt")
        
        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Caller Transkript
            text = event.get("transcript", "")
            logger.info(f"[OpenAI] Caller Transkript: {text[:100] if text else '(leer)'}...")
            if text and self.on_transcript:
                await self.on_transcript("caller", text, True)
        
        elif event_type == "response.audio_transcript.delta":
            # AI Transkript (streaming)
            text = event.get("delta", "")
            if text and self.on_transcript:
                await self.on_transcript("assistant", text, False)
        
        elif event_type == "response.audio_transcript.done":
            # AI Transkript fertig
            text = event.get("transcript", "")
            logger.info(f"[OpenAI] AI Antwort: {text[:100] if text else '(leer)'}...")
            if text and self.on_transcript:
                await self.on_transcript("assistant", text, True)
        
        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"[OpenAI] API Error: {error}")
        
        elif event_type in ["session.created", "session.updated"]:
            logger.info(f"[OpenAI] {event_type}")
        
        elif event_type == "response.created":
            logger.info("[OpenAI] AI beginnt zu antworten...")
        
        elif event_type == "response.done":
            logger.info("[OpenAI] AI Antwort abgeschlossen")
    
    async def send_audio(self, audio_data: bytes):
        """
        Audio an die API senden.
        
        Args:
            audio_data: PCM16 Audio @ 16kHz
        """
        if not self._ws or not self._running:
            return
        
        try:
            # Log erstes Audio-Paket
            if not hasattr(self, '_sent_audio_count'):
                self._sent_audio_count = 0
            self._sent_audio_count += 1
            
            if self._sent_audio_count == 1:
                # Erste paar Bytes für Debug
                import struct
                samples = struct.unpack(f'<{min(10, len(audio_data)//2)}h', audio_data[:min(20, len(audio_data))])
                logger.info(f"[OpenAI] Erstes Audio gesendet: {len(audio_data)} bytes, erste samples: {samples}")
            
            # Audio als Base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            await self._ws.send_str(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
            
        except Exception as e:
            logger.warning(f"Audio senden Fehler: {e}")
    
    async def commit_audio(self):
        """Audio Buffer committen (Turn beenden)."""
        if not self._ws or not self._running:
            return
        
        try:
            await self._ws.send_str(json.dumps({
                "type": "input_audio_buffer.commit"
            }))
        except Exception as e:
            logger.debug(f"Commit Fehler: {e}")
    
    def set_instructions(self, instructions: str):
        """Setzt neue Instruktionen (werden beim nächsten Anruf aktiv)."""
        self.instructions = instructions
        logger.info(f"Instruktionen aktualisiert ({len(instructions)} Zeichen)")
    
    async def disconnect(self):
        """Verbindung trennen."""
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            try:
                await self._ws.close()
            except:
                pass
            self._ws = None
        
        if hasattr(self, '_session') and self._session:
            try:
                await self._session.close()
            except:
                pass
            self._session = None
        
        logger.info("OpenAI Realtime API getrennt")
