"""
Lokales Audio-Modul für Mikrofon/Lautsprecher Tests.

Ermöglicht Tests der OpenAI Realtime API ohne SIP-Verbindung.
"""

import logging
import threading
import time
from typing import Callable, Optional
import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

from config import AudioConfig
from core.audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


class LocalAudioDevice:
    """
    Lokales Audio-Gerät für Mikrofon-Eingabe und Lautsprecher-Ausgabe.

    Verwendet sounddevice für plattformübergreifende Audio I/O.
    """

    def __init__(
        self,
        audio_config: AudioConfig,
        audio_in_buffer: AudioBuffer,
        audio_out_buffer: AudioBuffer,
    ):
        """
        Initialisiert das lokale Audio-Gerät.

        Args:
            audio_config: Audio-Einstellungen
            audio_in_buffer: Buffer für Mikrofon-Audio (-> AI)
            audio_out_buffer: Buffer für AI-Audio (-> Lautsprecher)
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice nicht installiert!")

        self._config = audio_config
        self._in_buffer = audio_in_buffer
        self._out_buffer = audio_out_buffer

        self._running = False
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.OutputStream] = None
        self._output_thread: Optional[threading.Thread] = None

        # Audio-Einstellungen
        self._sample_rate = audio_config.sample_rate  # 16kHz für Input
        self._output_sample_rate = 24000  # 24kHz für Output (API liefert 24kHz)
        self._channels = audio_config.channels
        self._frame_size = audio_config.frame_size
        self._output_frame_size = int(24000 * audio_config.frame_duration_ms / 1000)  # 480 für 20ms
        self._dtype = np.int16

        # Interner Puffer für Output-Audio (für variable Chunk-Größen)
        self._output_audio_buffer: list[np.ndarray] = []
        self._output_audio_buffer_samples = 0
        
        logger.info(f"LocalAudioDevice: Input {self._sample_rate}Hz, Output {self._output_sample_rate}Hz, "
                    f"{self._channels}ch, {self._config.frame_duration_ms}ms frames")

    def start(
        self,
        input_device: Optional[int] = None,
        output_device: Optional[int] = None,
    ) -> None:
        """
        Startet Audio-Aufnahme und -Wiedergabe.
        
        Args:
            input_device: ID des Mikrofons (None = Standard)
            output_device: ID des Lautsprechers (None = Standard)
        """
        if self._running:
            return

        self._running = True
        self._in_buffer.start()
        self._out_buffer.start()

        # Input Stream (Mikrofon)
        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            blocksize=self._frame_size,
            device=input_device,
            callback=self._input_callback,
        )
        self._input_stream.start()

        # Output Stream (Lautsprecher) - 24kHz für API Audio
        self._output_stream = sd.OutputStream(
            samplerate=self._output_sample_rate,
            channels=self._channels,
            dtype=self._dtype,
            blocksize=self._output_frame_size,
            device=output_device,
            callback=self._output_callback,
        )
        self._output_stream.start()

        input_name = f"Device {input_device}" if input_device else "Standard"
        output_name = f"Device {output_device}" if output_device else "Standard"
        logger.info(f"Lokales Audio gestartet (Input: {input_name}, Output: {output_name})")

    def stop(self) -> None:
        """Stoppt Audio-Aufnahme und -Wiedergabe."""
        self._running = False

        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None

        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None

        self._in_buffer.stop()
        self._out_buffer.stop()
        
        # Internen Puffer leeren
        self._output_audio_buffer = []
        self._output_audio_buffer_samples = 0

        logger.info("Lokales Audio gestoppt")

    def _input_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback für Mikrofon-Eingabe."""
        if status:
            logger.warning(f"Audio Input Status: {status}")

        if not self._running:
            return

        # Numpy Array zu bytes konvertieren
        pcm_data = indata.tobytes()

        # In Buffer pushen
        timestamp = time.time() * 1000
        self._in_buffer.push(pcm_data, timestamp_ms=timestamp)

    def _output_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback für Lautsprecher-Ausgabe."""
        if status:
            logger.warning(f"Audio Output Status: {status}")

        if not self._running:
            outdata.fill(0)
            return

        # Hole neue Daten aus dem Buffer und füge sie zum internen Puffer hinzu
        while True:
            frame = self._out_buffer.pull(timeout=0)
            if frame is None:
                break
            audio_data = np.frombuffer(frame.data, dtype=self._dtype)
            self._output_audio_buffer.append(audio_data)
            self._output_audio_buffer_samples += len(audio_data)
        
        # Genug Samples für diesen Frame?
        if self._output_audio_buffer_samples >= frames:
            # Alle Chunks zusammenfügen
            all_audio = np.concatenate(self._output_audio_buffer)
            
            # Die benötigten Samples ausgeben
            outdata[:, 0] = all_audio[:frames]
            
            # Rest behalten
            if len(all_audio) > frames:
                self._output_audio_buffer = [all_audio[frames:]]
                self._output_audio_buffer_samples = len(all_audio) - frames
            else:
                self._output_audio_buffer = []
                self._output_audio_buffer_samples = 0
            
            # Debug logging
            self._output_frames_played = getattr(self, '_output_frames_played', 0) + 1
            if self._output_frames_played % 100 == 1:
                logger.debug(f"Audio abgespielt: {self._output_frames_played} Frames")
        elif self._output_audio_buffer_samples > 0:
            # Teilweise gefüllt - ausgeben was wir haben
            all_audio = np.concatenate(self._output_audio_buffer)
            outdata[:len(all_audio), 0] = all_audio
            outdata[len(all_audio):, 0] = 0
            self._output_audio_buffer = []
            self._output_audio_buffer_samples = 0
        else:
            # Stille wenn kein Audio verfügbar
            outdata.fill(0)

    @staticmethod
    def list_devices() -> list[dict]:
        """Listet verfügbare Audio-Geräte auf."""
        if not SOUNDDEVICE_AVAILABLE:
            return []

        devices = []
        for i, dev in enumerate(sd.query_devices()):
            devices.append({
                "id": i,
                "name": dev["name"],
                "inputs": dev["max_input_channels"],
                "outputs": dev["max_output_channels"],
                "default_input": i == sd.default.device[0],
                "default_output": i == sd.default.device[1],
            })
        return devices

    @staticmethod
    def get_default_devices() -> tuple[int, int]:
        """Gibt Standard-Input und -Output Gerät zurück."""
        if not SOUNDDEVICE_AVAILABLE:
            return (-1, -1)
        return sd.default.device


# Demo/Test
if __name__ == "__main__":
    import sys
    from config import AudioConfig

    print("=== Local Audio Test ===")
    print(f"sounddevice verfügbar: {SOUNDDEVICE_AVAILABLE}")

    if not SOUNDDEVICE_AVAILABLE:
        print("sounddevice nicht installiert!")
        sys.exit(1)

    print("\nVerfügbare Geräte:")
    for dev in LocalAudioDevice.list_devices():
        marker = ""
        if dev["default_input"]:
            marker += " [DEFAULT INPUT]"
        if dev["default_output"]:
            marker += " [DEFAULT OUTPUT]"
        print(f"  {dev['id']}: {dev['name']} (in:{dev['inputs']}, out:{dev['outputs']}){marker}")

    print("\nStarte 5-Sekunden Echo-Test...")
    print("Sprechen Sie ins Mikrofon - Sie sollten sich selbst hören.")

    config = AudioConfig()
    in_buf = AudioBuffer(max_frames=50)
    out_buf = AudioBuffer(max_frames=50)

    device = LocalAudioDevice(config, in_buf, out_buf)
    device.start()

    # Echo: Input direkt zu Output
    def echo_loop():
        while device._running:
            frame = in_buf.pull(timeout=0.02)
            if frame:
                out_buf.push(frame.data, frame.timestamp_ms)

    echo_thread = threading.Thread(target=echo_loop, daemon=True)
    echo_thread.start()

    time.sleep(5)

    device.stop()
    print("Test beendet.")
