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


class AIClient:
    """
    Async Client für OpenAI Realtime API via WebSocket.
    """
    
    # Audio Formate
    INPUT_SAMPLE_RATE = 16000   # AI erwartet 16kHz
    OUTPUT_SAMPLE_RATE = 24000  # AI sendet 24kHz
    
    REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._ws = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        
        self.muted = False
        self.instructions = DEFAULT_INSTRUCTIONS
        
        # Event Callbacks
        self.on_audio_response: Optional[Callable[[bytes], None]] = None
        self.on_transcript: Optional[Callable[[str, str, bool], None]] = None
    
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
            
            session = aiohttp.ClientSession()
            self._ws = await session.ws_connect(
                self.REALTIME_URL,
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
        
        if event_type == "response.audio.delta":
            # Audio-Chunk empfangen
            audio_b64 = event.get("delta", "")
            if audio_b64 and not self.muted:
                audio_bytes = base64.b64decode(audio_b64)
                
                if self.on_audio_response:
                    await self.on_audio_response(audio_bytes)
        
        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Caller Transkript
            text = event.get("transcript", "")
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
            if text and self.on_transcript:
                await self.on_transcript("assistant", text, True)
        
        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"API Error: {error.get('message', 'Unknown error')}")
        
        elif event_type in ["session.created", "session.updated"]:
            logger.debug(f"Session Event: {event_type}")
    
    async def send_audio(self, audio_data: bytes):
        """
        Audio an die API senden.
        
        Args:
            audio_data: PCM16 Audio @ 16kHz
        """
        if not self._ws or not self._running:
            return
        
        try:
            # Audio als Base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            await self._ws.send_str(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }))
            
        except Exception as e:
            logger.debug(f"Audio senden Fehler: {e}")
    
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
