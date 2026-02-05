"""
Thread-safe Audio Buffer für Producer/Consumer Pattern.
"""

import queue
import threading
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AudioFrame:
    """Ein einzelner Audio-Frame."""

    data: bytes  # PCM 16-bit Daten
    timestamp_ms: float  # Zeitstempel in Millisekunden


class AudioBuffer:
    """
    Thread-safe Ringbuffer für Audio-Frames.

    Verwendet queue.Queue für Producer/Consumer Pattern.
    Begrenzte Größe verhindert unbegrenztes Wachstum bei Backpressure.
    """

    def __init__(
        self,
        max_frames: int = 15,  # ~300ms bei 20ms Frames
        frame_duration_ms: int = 20,
    ):
        """
        Initialisiert den Audio Buffer.

        Args:
            max_frames: Maximale Anzahl gepufferter Frames
            frame_duration_ms: Dauer eines Frames in Millisekunden
        """
        self._queue: queue.Queue[AudioFrame] = queue.Queue(maxsize=max_frames)
        self._max_frames = max_frames
        self._frame_duration_ms = frame_duration_ms
        self._running = False
        self._lock = threading.Lock()

        # Statistiken
        self._frames_pushed = 0
        self._frames_dropped = 0
        self._frames_pulled = 0

    @property
    def size(self) -> int:
        """Aktuelle Anzahl Frames im Buffer."""
        return self._queue.qsize()

    @property
    def max_size(self) -> int:
        """Maximale Kapazität."""
        return self._max_frames

    @property
    def buffer_ms(self) -> float:
        """Aktuell gepufferte Zeit in Millisekunden."""
        return self.size * self._frame_duration_ms

    @property
    def is_full(self) -> bool:
        """Prüft ob Buffer voll ist."""
        return self._queue.full()

    @property
    def is_empty(self) -> bool:
        """Prüft ob Buffer leer ist."""
        return self._queue.empty()

    def start(self) -> None:
        """Startet den Buffer für Operationen."""
        with self._lock:
            self._running = True
            self._frames_pushed = 0
            self._frames_dropped = 0
            self._frames_pulled = 0

    def stop(self) -> None:
        """Stoppt den Buffer und leert ihn."""
        with self._lock:
            self._running = False
        self.clear()

    def push(self, data: bytes, timestamp_ms: float = 0.0, block: bool = False) -> bool:
        """
        Fügt einen Frame zum Buffer hinzu.

        Args:
            data: PCM Audio-Daten
            timestamp_ms: Zeitstempel
            block: Wenn True, wartet bis Platz frei ist

        Returns:
            True wenn erfolgreich, False wenn Buffer voll (nur bei block=False)
        """
        if not self._running:
            return False

        frame = AudioFrame(data=data, timestamp_ms=timestamp_ms)

        try:
            self._queue.put(frame, block=block, timeout=0.1 if block else None)
            self._frames_pushed += 1
            return True
        except queue.Full:
            # Frame droppen bei vollem Buffer
            self._frames_dropped += 1
            if self._frames_dropped % 50 == 1:
                logger.warning(
                    f"Audio Buffer voll, Frame gedroppt (total: {self._frames_dropped})"
                )
            return False

    def pull(self, timeout: Optional[float] = 0.1) -> Optional[AudioFrame]:
        """
        Holt einen Frame aus dem Buffer.

        Args:
            timeout: Maximale Wartezeit in Sekunden, None für nicht-blockierend

        Returns:
            AudioFrame oder None wenn Buffer leer/gestoppt
        """
        if not self._running and self._queue.empty():
            return None

        try:
            frame = self._queue.get(block=timeout is not None, timeout=timeout)
            self._frames_pulled += 1
            return frame
        except queue.Empty:
            return None

    def clear(self) -> int:
        """
        Leert den Buffer.

        Returns:
            Anzahl entfernter Frames
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        return count

    def get_stats(self) -> dict:
        """
        Gibt Buffer-Statistiken zurück.

        Returns:
            Dict mit Statistiken
        """
        return {
            "size": self.size,
            "max_size": self._max_frames,
            "buffer_ms": self.buffer_ms,
            "frames_pushed": self._frames_pushed,
            "frames_dropped": self._frames_dropped,
            "frames_pulled": self._frames_pulled,
            "drop_rate": (
                self._frames_dropped / self._frames_pushed if self._frames_pushed > 0 else 0.0
            ),
        }


# Demo/Test
if __name__ == "__main__":
    import time

    buffer = AudioBuffer(max_frames=5, frame_duration_ms=20)
    buffer.start()

    # Producer
    print("Pushing 7 frames to buffer with max 5...")
    for i in range(7):
        success = buffer.push(f"frame_{i}".encode(), timestamp_ms=i * 20)
        print(f"  Frame {i}: {'OK' if success else 'DROPPED'}")

    print(f"\nBuffer size: {buffer.size}/{buffer.max_size}")
    print(f"Buffer time: {buffer.buffer_ms}ms")

    # Consumer
    print("\nPulling frames...")
    while True:
        frame = buffer.pull(timeout=0.01)
        if frame is None:
            break
        print(f"  Got: {frame.data.decode()}")

    print(f"\nStats: {buffer.get_stats()}")
    buffer.stop()
