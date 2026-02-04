"""
Audio Handler für Realtime API Integration.

Verbindet Audio-Buffer mit dem Realtime Client:
- Liest aus audio_in_buffer (Caller Audio)
- Sendet an Realtime API
- Empfängt Antwort-Audio
- Schreibt in audio_out_buffer
"""

import logging
import threading
import time
from typing import Optional
import numpy as np

from config import AudioConfig
from core.audio_buffer import AudioBuffer
from realtime_ai.client import RealtimeClient

logger = logging.getLogger(__name__)


class AudioHandler:
    """
    Verarbeitet Audio zwischen Buffern und Realtime API.

    Aufgaben:
    - Audio vom Caller zur API streamen
    - Antwort-Audio von API zum Caller streamen
    - Sample-Rate Konvertierung (16kHz <-> 24kHz)
    - Interruption Handling
    """

    def __init__(
        self,
        audio_config: AudioConfig,
        audio_in_buffer: AudioBuffer,
        audio_out_buffer: AudioBuffer,
        realtime_client: RealtimeClient,
    ):
        """
        Initialisiert den Audio Handler.

        Args:
            audio_config: Audio-Einstellungen
            audio_in_buffer: Buffer mit Caller Audio
            audio_out_buffer: Buffer für AI Antwort
            realtime_client: Realtime API Client
        """
        self._config = audio_config
        self._in_buffer = audio_in_buffer
        self._out_buffer = audio_out_buffer
        self._client = realtime_client

        self._running = False
        self._muted = False
        self._send_thread: Optional[threading.Thread] = None

        # Statistiken
        self._frames_sent = 0
        self._frames_received = 0

    def start(self) -> None:
        """Startet die Audio-Verarbeitung."""
        if self._running:
            return

        self._running = True

        # Callback für empfangenes Audio registrieren
        self._client.set_audio_callback(self._on_audio_received)

        # Thread zum Senden starten
        self._send_thread = threading.Thread(
            target=self._send_loop,
            name="AudioHandler-Send",
            daemon=True,
        )
        self._send_thread.start()

        logger.info("AudioHandler gestartet")

    def stop(self) -> None:
        """Stoppt die Audio-Verarbeitung."""
        self._running = False

        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=1.0)

        logger.info("AudioHandler gestoppt")

    def set_muted(self, muted: bool) -> None:
        """
        Setzt den Mute-Status für AI Audio.

        Args:
            muted: True um AI Audio zu unterdrücken
        """
        self._muted = muted

        if muted:
            # Aktuelle Antwort abbrechen
            self._client.cancel_response()
            # Output Buffer leeren
            self._out_buffer.clear()
            logger.info("AI Audio stummgeschaltet")
        else:
            logger.info("AI Audio aktiviert")

    def _send_loop(self) -> None:
        """Thread-Loop zum Senden von Audio an die API."""
        last_log_time = time.time()
        frames_since_log = 0
        
        logger.info("AudioHandler Send-Loop gestartet")
        
        while self._running:
            # Frame aus Input Buffer holen
            frame = self._in_buffer.pull(timeout=0.02)

            if frame is None:
                continue

            if not self._client.is_connected:
                # Warte auf Verbindung
                if frames_since_log == 0:
                    logger.debug("Warte auf Realtime API Verbindung...")
                continue

            try:
                # 16kHz zu 24kHz konvertieren (Realtime API erwartet 24kHz)
                pcm_24k = self._resample_to_24k(frame.data)

                # An API senden
                self._client.send_audio(pcm_24k)
                self._frames_sent += 1
                frames_since_log += 1
                
                # Log alle 2 Sekunden
                now = time.time()
                if now - last_log_time >= 2.0:
                    logger.info(f"AudioHandler: {self._frames_sent} Frames an API gesendet, Buffer: {self._in_buffer.size}")
                    last_log_time = now
                    frames_since_log = 0

            except Exception as e:
                logger.error(f"Fehler beim Audio-Senden: {e}")

    def _on_audio_received(self, pcm_data: bytes) -> None:
        """
        Callback für empfangenes Audio von der API.

        Args:
            pcm_data: 24kHz PCM Audio von der API
        """
        if self._muted:
            logger.debug("Audio empfangen aber muted")
            return

        try:
            # Direkt 24kHz Audio weitergeben (kein Resampling)
            # Der LocalAudioDevice wird auf 24kHz laufen
            timestamp = time.time() * 1000
            self._out_buffer.push(pcm_data, timestamp_ms=timestamp)
            self._frames_received += 1
            
            # Debug: Alle 50 Frames loggen
            if self._frames_received % 50 == 1:
                samples = len(pcm_data) // 2
                logger.info(f"AI Audio empfangen: {self._frames_received} Frames, {samples} samples, Buffer: {self._out_buffer.size}")

        except Exception as e:
            logger.error(f"Fehler beim Audio-Empfang: {e}")

    def _resample_to_24k(self, pcm_16k: bytes) -> bytes:
        """
        Resampled 16kHz Audio zu 24kHz für die API.

        Args:
            pcm_16k: 16kHz 16-bit PCM

        Returns:
            24kHz 16-bit PCM
        """
        samples = np.frombuffer(pcm_16k, dtype=np.int16)

        # Verhältnis 24/16 = 1.5
        new_length = int(len(samples) * 1.5)
        indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(samples)), samples)

        return resampled.astype(np.int16).tobytes()

    def _resample_to_16k(self, pcm_24k: bytes) -> bytes:
        """
        Resampled 24kHz Audio zu 16kHz für SIP.

        Args:
            pcm_24k: 24kHz 16-bit PCM

        Returns:
            16kHz 16-bit PCM
        """
        samples = np.frombuffer(pcm_24k, dtype=np.int16)

        # Verhältnis 16/24 = 0.667
        new_length = int(len(samples) * 16 / 24)
        indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(samples)), samples)

        return resampled.astype(np.int16).tobytes()

    def interrupt(self) -> None:
        """
        Unterbricht die aktuelle AI-Antwort.

        Wird aufgerufen wenn der Caller anfängt zu sprechen.
        """
        if not self._muted:
            self._client.cancel_response()
            self._out_buffer.clear()
            logger.debug("AI Antwort unterbrochen")

    def get_stats(self) -> dict:
        """Gibt Statistiken zurück."""
        return {
            "frames_sent": self._frames_sent,
            "frames_received": self._frames_received,
            "muted": self._muted,
            "in_buffer_size": self._in_buffer.size,
            "out_buffer_size": self._out_buffer.size,
        }


# Demo/Test
if __name__ == "__main__":
    from core.audio_buffer import AudioBuffer

    in_buf = AudioBuffer()
    out_buf = AudioBuffer()

    # Test Resampling
    print("Testing resampling...")

    # Dummy Handler für Resampling-Test
    class DummyClient:
        def is_connected(self):
            return False
        def set_audio_callback(self, cb):
            pass
        def send_audio(self, data):
            pass
        def cancel_response(self):
            pass

    from config import AudioConfig
    handler = AudioHandler(AudioConfig(), in_buf, out_buf, DummyClient())

    # Test 16k -> 24k
    samples_16k = 320  # 20ms @ 16kHz
    pcm_16k = np.zeros(samples_16k, dtype=np.int16).tobytes()
    pcm_24k = handler._resample_to_24k(pcm_16k)
    samples_24k = len(pcm_24k) // 2

    print(f"16kHz: {samples_16k} samples -> 24kHz: {samples_24k} samples")
    assert samples_24k == 480, f"Expected 480, got {samples_24k}"

    # Test 24k -> 16k
    pcm_back = handler._resample_to_16k(pcm_24k)
    samples_back = len(pcm_back) // 2

    print(f"24kHz: {samples_24k} samples -> 16kHz: {samples_back} samples")
    assert samples_back == 320, f"Expected 320, got {samples_back}"

    print("Resampling Test erfolgreich!")
