"""
Transcript Panel für Live-Transkription.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QColor

from core.signals import AppSignals


class TranscriptPanel(QWidget):
    """
    Panel für Live-Transkription.

    Zeigt:
    - Caller Text (streaming)
    - Assistant Text (streaming)
    - Copy/Export Buttons
    """

    def __init__(self, signals: AppSignals, parent: QWidget | None = None):
        super().__init__(parent)
        self._signals = signals
        self._transcript_text = ""
        self._current_partial: dict[str, str] = {"caller": "", "assistant": ""}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Live-Transkript")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._clear_btn = QPushButton("Löschen")
        self._clear_btn.setStyleSheet(
            "QPushButton { padding: 5px 10px; border-radius: 3px; }"
        )
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        header_layout.addWidget(self._clear_btn)

        self._copy_btn = QPushButton("Kopieren")
        self._copy_btn.setStyleSheet(
            "QPushButton { padding: 5px 10px; border-radius: 3px; }"
        )
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        header_layout.addWidget(self._copy_btn)

        self._export_btn = QPushButton("Exportieren")
        self._export_btn.setStyleSheet(
            "QPushButton { padding: 5px 10px; border-radius: 3px; }"
        )
        self._export_btn.clicked.connect(self._on_export_clicked)
        header_layout.addWidget(self._export_btn)

        layout.addLayout(header_layout)

        # Transcript Text Area
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 11))
        self._text_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
            "border: 1px solid #3c3c3c; border-radius: 5px; padding: 10px; }"
        )
        self._text_edit.setPlaceholderText(
            "Transkript erscheint hier, sobald der Anruf aktiv ist..."
        )
        layout.addWidget(self._text_edit, stretch=1)

        # Status Bar
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)

        self._status_label = QLabel("Bereit")
        self._status_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        self._word_count_label = QLabel("0 Wörter")
        self._word_count_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self._word_count_label)

        layout.addWidget(status_frame)

    def _connect_signals(self) -> None:
        """Verbindet die Signals."""
        self._signals.transcript_updated.connect(self._on_transcript_updated)
        self._signals.transcript_cleared.connect(self._on_transcript_cleared)

    def _on_transcript_updated(self, speaker: str, text: str, is_final: bool) -> None:
        """
        Handler für Transkript-Updates.

        Args:
            speaker: "caller" oder "assistant"
            text: Der Text
            is_final: True wenn finalisiert, False wenn partial
        """
        if is_final:
            # Finalen Text zum Transkript hinzufügen
            self._add_final_segment(speaker, text)
            self._current_partial[speaker] = ""
        else:
            # Partial Update
            self._current_partial[speaker] = text
            self._update_display()

        self._update_status()

    def _add_final_segment(self, speaker: str, text: str) -> None:
        """Fügt ein finalisiertes Segment hinzu."""
        speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
        color = "#61afef" if speaker == "caller" else "#98c379"

        # Zum Transcript Text hinzufügen
        self._transcript_text += f"[{speaker_label}] {text}\n"

        # Anzeige aktualisieren
        self._update_display()

    def _update_display(self) -> None:
        """Aktualisiert die Textanzeige mit finalem Text und Partials."""
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Basis-Text setzen
        display_text = self._transcript_text

        # Partials anhängen (kursiv)
        for speaker, partial in self._current_partial.items():
            if partial:
                speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
                display_text += f"[{speaker_label}] {partial}...\n"

        self._text_edit.setPlainText(display_text)

        # Scroll to bottom
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text_edit.setTextCursor(cursor)

    def _update_status(self) -> None:
        """Aktualisiert die Statusleiste."""
        word_count = len(self._transcript_text.split())
        self._word_count_label.setText(f"{word_count} Wörter")

    def _on_transcript_cleared(self) -> None:
        """Handler für Transkript löschen."""
        self._transcript_text = ""
        self._current_partial = {"caller": "", "assistant": ""}
        self._text_edit.clear()
        self._update_status()

    def _on_clear_clicked(self) -> None:
        """Handler für Clear Button."""
        self._signals.transcript_cleared.emit()

    def _on_copy_clicked(self) -> None:
        """Handler für Copy Button."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(self._transcript_text)
        self._status_label.setText("In Zwischenablage kopiert!")

    def _on_export_clicked(self) -> None:
        """Handler für Export Button."""
        if not self._transcript_text:
            QMessageBox.information(self, "Export", "Kein Transkript zum Exportieren.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Transkript exportieren",
            "transcript.txt",
            "Text Dateien (*.txt);;Alle Dateien (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self._transcript_text)
                self._status_label.setText(f"Exportiert nach: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen: {e}")

    def get_transcript(self) -> str:
        """Gibt das aktuelle Transkript zurück."""
        return self._transcript_text
