"""
Transcript Manager für Live-Transkription.

Verwaltet Transkript-Segmente von Caller und Assistant,
führt Partials zusammen und ermöglicht Export.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional
from pathlib import Path

from core.signals import AppSignals

logger = logging.getLogger(__name__)


Speaker = Literal["caller", "assistant"]


@dataclass
class TranscriptSegment:
    """Ein einzelnes Transkript-Segment."""

    speaker: Speaker
    text: str
    is_final: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        speaker_label = "Anrufer" if self.speaker == "caller" else "Assistent"
        return f"[{speaker_label}] {self.text}"


class TranscriptManager:
    """
    Verwaltet das Live-Transkript eines Anrufs.

    Aufgaben:
    - Partial Updates empfangen und zusammenführen
    - Finale Segmente speichern
    - Transkript formatieren und exportieren
    """

    def __init__(self, signals: Optional[AppSignals] = None):
        """
        Initialisiert den Transcript Manager.

        Args:
            signals: Qt Signals für UI-Updates (optional)
        """
        self._signals = signals
        self._segments: list[TranscriptSegment] = []
        self._current_partials: dict[Speaker, str] = {"caller": "", "assistant": ""}
        self._call_start: Optional[datetime] = None

    def start_new_call(self) -> None:
        """Startet ein neues Transkript für einen Anruf."""
        self._segments = []
        self._current_partials = {"caller": "", "assistant": ""}
        self._call_start = datetime.now()
        logger.info("Neues Transkript gestartet")

    def add_partial(self, speaker: Speaker, text: str) -> None:
        """
        Fügt einen partiellen Text hinzu (nicht finalisiert).

        Args:
            speaker: "caller" oder "assistant"
            text: Partieller Text
        """
        self._current_partials[speaker] = text

        if self._signals:
            self._signals.transcript_updated.emit(speaker, text, False)

    def add_final(self, speaker: Speaker, text: str) -> None:
        """
        Fügt einen finalisierten Text hinzu.

        Args:
            speaker: "caller" oder "assistant"
            text: Finaler Text
        """
        if not text.strip():
            return

        segment = TranscriptSegment(
            speaker=speaker,
            text=text.strip(),
            is_final=True,
        )
        self._segments.append(segment)
        self._current_partials[speaker] = ""

        if self._signals:
            self._signals.transcript_updated.emit(speaker, text, True)

        logger.debug(f"Segment hinzugefügt: {segment}")

    def update(self, speaker: Speaker, text: str, is_final: bool) -> None:
        """
        Universelle Update-Methode.

        Args:
            speaker: "caller" oder "assistant"
            text: Text
            is_final: True wenn finalisiert
        """
        if is_final:
            self.add_final(speaker, text)
        else:
            self.add_partial(speaker, text)

    def clear(self) -> None:
        """Löscht das gesamte Transkript."""
        self._segments = []
        self._current_partials = {"caller": "", "assistant": ""}

        if self._signals:
            self._signals.transcript_cleared.emit()

        logger.info("Transkript gelöscht")

    def get_segments(self) -> list[TranscriptSegment]:
        """Gibt alle finalisierten Segmente zurück."""
        return self._segments.copy()

    def get_current_partial(self, speaker: Speaker) -> str:
        """Gibt den aktuellen partiellen Text für einen Sprecher zurück."""
        return self._current_partials.get(speaker, "")

    def get_formatted_transcript(self, include_timestamps: bool = False) -> str:
        """
        Gibt das formatierte Transkript als String zurück.

        Args:
            include_timestamps: Ob Zeitstempel einbezogen werden sollen

        Returns:
            Formatierter Transkript-String
        """
        lines = []

        if self._call_start and include_timestamps:
            lines.append(f"Anruf vom {self._call_start.strftime('%d.%m.%Y %H:%M:%S')}")
            lines.append("-" * 40)

        for segment in self._segments:
            if include_timestamps:
                timestamp = segment.timestamp.strftime("%H:%M:%S")
                speaker_label = "Anrufer" if segment.speaker == "caller" else "Assistent"
                lines.append(f"[{timestamp}] {speaker_label}: {segment.text}")
            else:
                lines.append(str(segment))

        # Aktuelle Partials anhängen
        for speaker, partial in self._current_partials.items():
            if partial:
                speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
                lines.append(f"[{speaker_label}] {partial}...")

        return "\n".join(lines)

    def export_to_file(
        self,
        file_path: str | Path,
        include_timestamps: bool = True,
    ) -> bool:
        """
        Exportiert das Transkript in eine Datei.

        Args:
            file_path: Pfad zur Ausgabedatei
            include_timestamps: Ob Zeitstempel einbezogen werden sollen

        Returns:
            True wenn erfolgreich
        """
        try:
            path = Path(file_path)
            content = self.get_formatted_transcript(include_timestamps)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Transkript exportiert nach: {path}")
            return True

        except Exception as e:
            logger.error(f"Export fehlgeschlagen: {e}")
            return False

    def get_word_count(self) -> int:
        """Gibt die Anzahl der Wörter im Transkript zurück."""
        total = 0
        for segment in self._segments:
            total += len(segment.text.split())
        return total

    def get_turn_count(self) -> dict[Speaker, int]:
        """Gibt die Anzahl der Sprecherwechsel zurück."""
        counts: dict[Speaker, int] = {"caller": 0, "assistant": 0}
        for segment in self._segments:
            counts[segment.speaker] += 1
        return counts

    def get_duration(self) -> Optional[float]:
        """
        Gibt die Dauer des Transkripts in Sekunden zurück.

        Returns:
            Dauer in Sekunden oder None wenn keine Segmente vorhanden
        """
        if not self._segments or not self._call_start:
            return None

        last_segment = self._segments[-1]
        return (last_segment.timestamp - self._call_start).total_seconds()

    def get_summary(self) -> dict:
        """Gibt eine Zusammenfassung des Transkripts zurück."""
        turns = self.get_turn_count()
        return {
            "segments": len(self._segments),
            "words": self.get_word_count(),
            "caller_turns": turns["caller"],
            "assistant_turns": turns["assistant"],
            "duration_seconds": self.get_duration(),
        }


# Demo/Test
if __name__ == "__main__":
    import time

    print("TranscriptManager Test")

    manager = TranscriptManager()
    manager.start_new_call()

    # Simuliere Gespräch
    print("\nSimuliere Gespräch...")

    # Caller spricht
    manager.add_partial("caller", "Hallo, ich")
    time.sleep(0.1)
    manager.add_partial("caller", "Hallo, ich möchte")
    time.sleep(0.1)
    manager.add_final("caller", "Hallo, ich möchte eine Pizza bestellen")

    # Assistant antwortet
    manager.add_partial("assistant", "Guten Tag!")
    time.sleep(0.1)
    manager.add_final("assistant", "Guten Tag! Welche Pizza darf es sein?")

    # Caller bestellt
    manager.add_final("caller", "Eine Margherita bitte")

    # Assistant bestätigt
    manager.add_final("assistant", "Eine Margherita, kommt sofort!")

    # Transkript ausgeben
    print("\n" + "=" * 40)
    print("TRANSKRIPT:")
    print("=" * 40)
    print(manager.get_formatted_transcript(include_timestamps=True))

    # Statistiken
    print("\n" + "=" * 40)
    print("STATISTIKEN:")
    print("=" * 40)
    summary = manager.get_summary()
    print(f"Segmente: {summary['segments']}")
    print(f"Wörter: {summary['words']}")
    print(f"Caller Turns: {summary['caller_turns']}")
    print(f"Assistant Turns: {summary['assistant_turns']}")

    print("\nTest abgeschlossen!")
