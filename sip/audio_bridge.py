"""
Audio Bridge für SIP/RTP Audio I/O.

Konvertiert zwischen SIP-Codec (typisch G.711/PCMU) und
internem Format (16kHz mono PCM).
"""

import logging
import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass
import numpy as np

from config import AudioConfig
from core.audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


@dataclass
class AudioStats:
    """Statistiken für Audio-Verarbeitung."""

    frames_received: int = 0
    frames_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    resample_errors: int = 0


class AudioBridge:
    """
    Bridge zwischen SIP Audio und internen Audio-Buffern.

    Aufgaben:
    - Empfängt RTP Audio vom SIP Stack
    - Konvertiert zu 16kHz mono PCM
    - Pusht in audio_in_buffer (für AI)
    - Holt Audio aus audio_out_buffer (von AI)
    - Konvertiert zurück zu SIP Codec Format
    - Sendet an SIP Stack

    Typisches Audio-Format:
    - SIP/RTP: 8kHz PCMU (G.711 u-law) oder PCMA (a-law)
    - Intern: 16kHz mono 16-bit PCM (linear)
    """

    def __init__(
        self,
        audio_config: AudioConfig,
        audio_in_buffer: AudioBuffer,
        audio_out_buffer: AudioBuffer,
    ):
        """
        Initialisiert die Audio Bridge.

        Args:
            audio_config: Audio-Einstellungen
            audio_in_buffer: Buffer für eingehende Audio (Caller -> AI)
            audio_out_buffer: Buffer für ausgehende Audio (AI -> Caller)
        """
        self._config = audio_config
        self._in_buffer = audio_in_buffer
        self._out_buffer = audio_out_buffer

        self._running = False
        self._in_thread: Optional[threading.Thread] = None
        self._out_thread: Optional[threading.Thread] = None

        self._stats = AudioStats()
        self._lock = threading.Lock()

        # Callbacks
        self._on_send_to_sip: Optional[Callable[[bytes], None]] = None

    def start(self) -> None:
        """Startet die Audio-Verarbeitung."""
        if self._running:
            return

        self._running = True
        self._in_buffer.start()
        self._out_buffer.start()

        # Output Thread (Audio von AI zu SIP)
        self._out_thread = threading.Thread(
            target=self._output_loop,
            name="AudioBridge-Out",
            daemon=True,
        )
        self._out_thread.start()

        logger.info("AudioBridge gestartet")

    def stop(self) -> None:
        """Stoppt die Audio-Verarbeitung."""
        self._running = False

        self._in_buffer.stop()
        self._out_buffer.stop()

        # Threads beenden
        if self._out_thread and self._out_thread.is_alive():
            self._out_thread.join(timeout=1.0)

        logger.info("AudioBridge gestoppt")

    def receive_from_sip(self, audio_data: bytes, codec: str = "PCMU") -> None:
        """
        Empfängt Audio vom SIP Stack.

        Args:
            audio_data: Rohe Audio-Daten vom RTP
            codec: Audio-Codec (PCMU, PCMA, L16)
        """
        if not self._running:
            return

        try:
            # Codec dekodieren und zu 16kHz PCM konvertieren
            pcm_data = self._decode_audio(audio_data, codec)

            # In Buffer pushen
            timestamp = time.time() * 1000
            self._in_buffer.push(pcm_data, timestamp_ms=timestamp)

            with self._lock:
                self._stats.frames_received += 1
                self._stats.bytes_received += len(audio_data)
                
                # Log alle 100 Frames
                if self._stats.frames_received % 100 == 1:
                    logger.info(f"AudioBridge: {self._stats.frames_received} Frames empfangen, "
                               f"In-Buffer: {self._in_buffer.size}, Out-Buffer: {self._out_buffer.size}")

        except Exception as e:
            logger.error(f"Fehler beim Audio-Empfang: {e}")
            with self._lock:
                self._stats.resample_errors += 1

    def set_sip_output_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Setzt Callback für ausgehende SIP Audio.

        Args:
            callback: Funktion die mit encodierten Audio-Daten aufgerufen wird
        """
        self._on_send_to_sip = callback

    def _output_loop(self) -> None:
        """Thread-Loop für ausgehende Audio."""
        while self._running:
            frame = self._out_buffer.pull(timeout=0.02)

            if frame is None:
                continue

            try:
                # PCM zu SIP Codec konvertieren
                encoded = self._encode_audio(frame.data, "PCMU")

                # An SIP senden
                if self._on_send_to_sip:
                    self._on_send_to_sip(encoded)

                with self._lock:
                    self._stats.frames_sent += 1
                    self._stats.bytes_sent += len(encoded)

            except Exception as e:
                logger.error(f"Fehler beim Audio-Senden: {e}")

    def _decode_audio(self, data: bytes, codec: str) -> bytes:
        """
        Dekodiert Audio von SIP-Codec zu 16kHz PCM.

        Args:
            data: Encodierte Audio-Daten
            codec: Codec-Name (PCMU, PCMA, L16)

        Returns:
            16kHz mono 16-bit PCM
        """
        if codec == "PCMU":
            # G.711 u-law zu linear PCM
            pcm = self._ulaw_to_linear(data)
            # 8kHz zu 16kHz resampling
            return self._resample(pcm, 8000, 16000)

        elif codec == "PCMA":
            # G.711 a-law zu linear PCM
            pcm = self._alaw_to_linear(data)
            return self._resample(pcm, 8000, 16000)

        elif codec == "L16":
            # Bereits linear PCM, nur resampling wenn nötig
            return data

        else:
            logger.warning(f"Unbekannter Codec: {codec}, verwende raw")
            return data

    def _encode_audio(self, data: bytes, codec: str) -> bytes:
        """
        Encodiert 16kHz PCM zu SIP-Codec.

        Args:
            data: 16kHz mono 16-bit PCM
            codec: Ziel-Codec

        Returns:
            Encodierte Audio-Daten
        """
        if codec == "PCMU":
            # 16kHz zu 8kHz downsample
            pcm_8k = self._resample(data, 16000, 8000)
            # Linear zu u-law
            return self._linear_to_ulaw(pcm_8k)

        elif codec == "PCMA":
            pcm_8k = self._resample(data, 16000, 8000)
            return self._linear_to_alaw(pcm_8k)

        elif codec == "L16":
            return data

        else:
            return data

    def _resample(self, data: bytes, from_rate: int, to_rate: int) -> bytes:
        """
        Resampled Audio zwischen Sample-Raten.

        Args:
            data: 16-bit PCM Daten
            from_rate: Quell-Sample-Rate
            to_rate: Ziel-Sample-Rate

        Returns:
            Resampelte PCM Daten
        """
        if from_rate == to_rate:
            return data

        # Bytes zu numpy array
        samples = np.frombuffer(data, dtype=np.int16)

        # Resample mit linearer Interpolation
        ratio = to_rate / from_rate
        new_length = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(samples)), samples)

        return resampled.astype(np.int16).tobytes()

    def _ulaw_to_linear(self, data: bytes) -> bytes:
        """Konvertiert G.711 u-law zu 16-bit linear PCM."""
        # u-law Dekodierungstabelle
        ULAW_TABLE = self._get_ulaw_decode_table()

        samples = []
        for byte in data:
            samples.append(ULAW_TABLE[byte])

        return np.array(samples, dtype=np.int16).tobytes()

    def _linear_to_ulaw(self, data: bytes) -> bytes:
        """Konvertiert 16-bit linear PCM zu G.711 u-law."""
        samples = np.frombuffer(data, dtype=np.int16)
        encoded = []

        for sample in samples:
            encoded.append(self._encode_ulaw_sample(sample))

        return bytes(encoded)

    def _alaw_to_linear(self, data: bytes) -> bytes:
        """Konvertiert G.711 a-law zu 16-bit linear PCM."""
        # Vereinfachte Implementierung
        ALAW_TABLE = self._get_alaw_decode_table()

        samples = []
        for byte in data:
            samples.append(ALAW_TABLE[byte])

        return np.array(samples, dtype=np.int16).tobytes()

    def _linear_to_alaw(self, data: bytes) -> bytes:
        """Konvertiert 16-bit linear PCM zu G.711 a-law."""
        samples = np.frombuffer(data, dtype=np.int16)
        encoded = []

        for sample in samples:
            encoded.append(self._encode_alaw_sample(sample))

        return bytes(encoded)

    @staticmethod
    def _get_ulaw_decode_table() -> list[int]:
        """Generiert u-law Dekodierungstabelle."""
        table = []
        for i in range(256):
            # Invertiere alle Bits
            byte = ~i & 0xFF

            # Extrahiere Komponenten
            sign = (byte & 0x80) >> 7
            exponent = (byte & 0x70) >> 4
            mantissa = byte & 0x0F

            # Berechne Sample
            sample = ((mantissa << 3) + 0x84) << exponent
            sample -= 0x84

            if sign:
                sample = -sample

            table.append(sample)

        return table

    @staticmethod
    def _get_alaw_decode_table() -> list[int]:
        """Generiert a-law Dekodierungstabelle."""
        table = []
        for i in range(256):
            byte = i ^ 0x55

            sign = (byte & 0x80) >> 7
            exponent = (byte & 0x70) >> 4
            mantissa = byte & 0x0F

            if exponent == 0:
                sample = (mantissa << 4) + 8
            else:
                sample = ((mantissa << 4) + 0x108) << (exponent - 1)

            if sign:
                sample = -sample

            table.append(sample)

        return table

    @staticmethod
    def _encode_ulaw_sample(sample: int) -> int:
        """Encodiert einen Sample-Wert zu u-law."""
        BIAS = 0x84
        CLIP = 32635

        # Clipping
        if sample > CLIP:
            sample = CLIP
        elif sample < -CLIP:
            sample = -CLIP

        # Vorzeichen extrahieren
        if sample < 0:
            sign = 0x80
            sample = -sample
        else:
            sign = 0

        sample += BIAS

        # Exponent finden
        exponent = 7
        exp_mask = 0x4000
        for _ in range(8):
            if sample & exp_mask:
                break
            exponent -= 1
            exp_mask >>= 1

        # Mantisse extrahieren
        mantissa = (sample >> (exponent + 3)) & 0x0F

        # u-law Byte zusammensetzen
        ulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF

        return ulaw_byte

    @staticmethod
    def _encode_alaw_sample(sample: int) -> int:
        """Encodiert einen Sample-Wert zu a-law."""
        CLIP = 32635

        if sample > CLIP:
            sample = CLIP
        elif sample < -CLIP:
            sample = -CLIP

        if sample < 0:
            sign = 0x80
            sample = -sample
        else:
            sign = 0

        if sample < 256:
            exponent = 0
            mantissa = sample >> 4
        else:
            exponent = 1
            while sample >= (512 << exponent):
                exponent += 1
                if exponent >= 7:
                    break
            mantissa = (sample >> (exponent + 3)) & 0x0F

        alaw_byte = (sign | (exponent << 4) | mantissa) ^ 0x55

        return alaw_byte

    def get_stats(self) -> dict:
        """Gibt Audio-Statistiken zurück."""
        with self._lock:
            return {
                "frames_received": self._stats.frames_received,
                "frames_sent": self._stats.frames_sent,
                "bytes_received": self._stats.bytes_received,
                "bytes_sent": self._stats.bytes_sent,
                "resample_errors": self._stats.resample_errors,
                "in_buffer_size": self._in_buffer.size,
                "out_buffer_size": self._out_buffer.size,
            }


# Demo/Test
if __name__ == "__main__":
    from config import AudioConfig
    from core.audio_buffer import AudioBuffer

    config = AudioConfig()
    in_buffer = AudioBuffer()
    out_buffer = AudioBuffer()

    bridge = AudioBridge(config, in_buffer, out_buffer)

    # Test Resampling
    print("Testing audio conversion...")

    # Erstelle Test-Audio (1kHz Sinuston, 8kHz, 20ms)
    duration_s = 0.02
    freq = 1000
    sample_rate = 8000
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    samples = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
    pcm_8k = samples.tobytes()

    print(f"Input: {len(pcm_8k)} bytes @ 8kHz ({len(samples)} samples)")

    # Resample zu 16kHz
    pcm_16k = bridge._resample(pcm_8k, 8000, 16000)
    samples_16k = np.frombuffer(pcm_16k, dtype=np.int16)
    print(f"Output: {len(pcm_16k)} bytes @ 16kHz ({len(samples_16k)} samples)")

    # Test u-law encoding/decoding
    print("\nTesting u-law codec...")
    ulaw = bridge._linear_to_ulaw(pcm_8k)
    decoded = bridge._ulaw_to_linear(ulaw)
    print(f"u-law: {len(ulaw)} bytes")
    print(f"Decoded: {len(decoded)} bytes")

    print("\nAudio Bridge Test erfolgreich!")
