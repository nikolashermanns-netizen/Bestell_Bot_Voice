"""
Voice Activity Detection (VAD) für Turn-Handling.

Erkennt wenn der Caller spricht, um:
- AI Audio zu unterbrechen
- Natürlichere Dialoge zu ermöglichen
"""

import logging
from typing import Callable, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Versuche webrtcvad zu importieren
try:
    import webrtcvad

    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    logger.warning("webrtcvad nicht verfügbar - verwende einfache Pegel-Erkennung")


@dataclass
class VADConfig:
    """Konfiguration für Voice Activity Detection."""

    # WebRTC VAD Aggressivität (0-3, höher = aggressiver)
    aggressiveness: int = 2

    # Sample-Rate (muss 8000, 16000, 32000 oder 48000 sein für webrtcvad)
    sample_rate: int = 16000

    # Frame-Dauer in ms (muss 10, 20 oder 30 sein für webrtcvad)
    frame_duration_ms: int = 20

    # Schwellwert für einfache Pegel-Erkennung (RMS)
    energy_threshold: float = 500.0

    # Minimum aufeinanderfolgende Frames für Spracherkennung
    min_speech_frames: int = 3

    # Minimum aufeinanderfolgende Frames für Stille-Erkennung
    min_silence_frames: int = 10


class VADDetector:
    """
    Voice Activity Detector.

    Verwendet webrtcvad wenn verfügbar, sonst einfache Energie-basierte Erkennung.
    """

    def __init__(self, config: VADConfig | None = None):
        """
        Initialisiert den VAD Detector.

        Args:
            config: VAD Konfiguration
        """
        self._config = config or VADConfig()

        self._is_speaking = False
        self._speech_frame_count = 0
        self._silence_frame_count = 0

        # Callbacks
        self._on_speech_start: Optional[Callable[[], None]] = None
        self._on_speech_end: Optional[Callable[[], None]] = None

        if WEBRTCVAD_AVAILABLE:
            self._vad = webrtcvad.Vad(self._config.aggressiveness)
            logger.info(f"WebRTC VAD initialisiert (Aggressivität: {self._config.aggressiveness})")
        else:
            self._vad = None
            logger.info("Energie-basierte VAD initialisiert")

    def process_frame(self, pcm_data: bytes) -> bool:
        """
        Verarbeitet einen Audio-Frame und erkennt Sprachaktivität.

        Args:
            pcm_data: 16-bit PCM Audio-Daten

        Returns:
            True wenn Sprache erkannt wurde
        """
        if WEBRTCVAD_AVAILABLE and self._vad:
            is_speech = self._process_webrtc(pcm_data)
        else:
            is_speech = self._process_energy(pcm_data)

        # State Machine für stabile Erkennung
        self._update_state(is_speech)

        return self._is_speaking

    def _process_webrtc(self, pcm_data: bytes) -> bool:
        """Verarbeitet mit WebRTC VAD."""
        try:
            # webrtcvad erwartet spezifische Frame-Größen
            frame_bytes = int(
                self._config.sample_rate * self._config.frame_duration_ms / 1000 * 2
            )

            # Falls Frame zu groß, nur passenden Teil nehmen
            if len(pcm_data) > frame_bytes:
                pcm_data = pcm_data[:frame_bytes]
            elif len(pcm_data) < frame_bytes:
                # Padding falls zu klein
                pcm_data = pcm_data + bytes(frame_bytes - len(pcm_data))

            return self._vad.is_speech(pcm_data, self._config.sample_rate)

        except Exception as e:
            logger.warning(f"WebRTC VAD Fehler: {e}, fallback auf Energie")
            return self._process_energy(pcm_data)

    def _process_energy(self, pcm_data: bytes) -> bool:
        """Verarbeitet mit einfacher Energie-Erkennung."""
        # PCM zu numpy
        samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)

        if len(samples) == 0:
            return False

        # RMS (Root Mean Square) berechnen
        rms = np.sqrt(np.mean(samples**2))

        return rms > self._config.energy_threshold

    def _update_state(self, is_speech: bool) -> None:
        """Aktualisiert den Sprach-Status mit Hysterese."""
        if is_speech:
            self._speech_frame_count += 1
            self._silence_frame_count = 0

            # Sprache beginnt nach min_speech_frames
            if (
                not self._is_speaking
                and self._speech_frame_count >= self._config.min_speech_frames
            ):
                self._is_speaking = True
                logger.debug("Sprache erkannt - START")
                if self._on_speech_start:
                    self._on_speech_start()

        else:
            self._silence_frame_count += 1
            self._speech_frame_count = 0

            # Stille beginnt nach min_silence_frames
            if (
                self._is_speaking
                and self._silence_frame_count >= self._config.min_silence_frames
            ):
                self._is_speaking = False
                logger.debug("Stille erkannt - END")
                if self._on_speech_end:
                    self._on_speech_end()

    def set_callbacks(
        self,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Setzt Callbacks für Sprache Start/Ende.

        Args:
            on_speech_start: Wird aufgerufen wenn Sprache beginnt
            on_speech_end: Wird aufgerufen wenn Sprache endet
        """
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end

    def reset(self) -> None:
        """Setzt den Detector zurück."""
        self._is_speaking = False
        self._speech_frame_count = 0
        self._silence_frame_count = 0

    @property
    def is_speaking(self) -> bool:
        """Gibt zurück ob aktuell Sprache erkannt wird."""
        return self._is_speaking

    def set_threshold(self, threshold: float) -> None:
        """Setzt den Energie-Schwellwert (für nicht-webrtcvad Modus)."""
        self._config.energy_threshold = threshold

    def set_aggressiveness(self, level: int) -> None:
        """Setzt die VAD Aggressivität (0-3)."""
        level = max(0, min(3, level))
        self._config.aggressiveness = level

        if self._vad:
            self._vad.set_mode(level)


class InterruptionHandler:
    """
    Behandelt Unterbrechungen der AI-Antwort.

    Verwendet VAD um zu erkennen wann der Caller spricht
    und unterbricht dann die laufende AI-Antwort.
    """

    def __init__(
        self,
        vad: VADDetector,
        on_interrupt: Callable[[], None],
    ):
        """
        Initialisiert den Interruption Handler.

        Args:
            vad: VAD Detector Instanz
            on_interrupt: Callback wenn Unterbrechung erkannt
        """
        self._vad = vad
        self._on_interrupt = on_interrupt

        self._ai_is_speaking = False
        self._interrupted = False

        # VAD Callbacks setzen
        self._vad.set_callbacks(
            on_speech_start=self._on_caller_speech_start,
            on_speech_end=self._on_caller_speech_end,
        )

    def set_ai_speaking(self, is_speaking: bool) -> None:
        """
        Setzt den AI-Sprech-Status.

        Args:
            is_speaking: True wenn AI gerade spricht
        """
        self._ai_is_speaking = is_speaking

        if not is_speaking:
            self._interrupted = False

    def process_frame(self, pcm_data: bytes) -> None:
        """
        Verarbeitet einen Audio-Frame für Interruption-Erkennung.

        Args:
            pcm_data: Caller Audio-Daten
        """
        self._vad.process_frame(pcm_data)

    def _on_caller_speech_start(self) -> None:
        """Callback wenn Caller anfängt zu sprechen."""
        if self._ai_is_speaking and not self._interrupted:
            logger.info("Caller unterbricht AI")
            self._interrupted = True
            self._on_interrupt()

    def _on_caller_speech_end(self) -> None:
        """Callback wenn Caller aufhört zu sprechen."""
        pass  # Derzeit keine Aktion nötig


# Demo/Test
if __name__ == "__main__":
    import time

    print("VAD Test")
    print(f"WebRTC VAD verfügbar: {WEBRTCVAD_AVAILABLE}")

    vad = VADDetector()

    # Callbacks
    def on_start():
        print(">>> SPRACHE START")

    def on_end():
        print(">>> SPRACHE ENDE")

    vad.set_callbacks(on_start, on_end)

    # Simuliere Audio-Frames
    print("\nSimuliere Stille...")
    silence = bytes(640)  # 20ms @ 16kHz
    for _ in range(10):
        vad.process_frame(silence)

    print("\nSimuliere Sprache (Rauschen)...")
    for _ in range(10):
        # Zufälliges Rauschen als "Sprache"
        noise = (np.random.randn(320) * 2000).astype(np.int16).tobytes()
        vad.process_frame(noise)

    print("\nSimuliere Stille...")
    for _ in range(15):
        vad.process_frame(silence)

    print("\nVAD Test abgeschlossen")
