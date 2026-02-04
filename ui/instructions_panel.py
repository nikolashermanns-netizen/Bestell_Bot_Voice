"""
Instructions Panel - Ermöglicht das Bearbeiten der AI-Instruktionen.
"""

import logging
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class InstructionsPanel(QWidget):
    """
    Panel zum Bearbeiten der AI-Instruktionen.
    
    Zeigt den aktuellen Kontext an und erlaubt Änderungen.
    """
    
    # Signal wenn Instruktionen geändert werden
    instructions_changed = Signal(str)
    
    def __init__(
        self,
        parent: QWidget | None = None,
        on_save: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self._on_save = on_save
        self._original_text = ""
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Erstellt die UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("🤖 AI-Instruktionen")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Buttons
        self._reset_btn = QPushButton("↩️ Zurücksetzen")
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setEnabled(False)
        header_layout.addWidget(self._reset_btn)
        
        self._save_btn = QPushButton("💾 Speichern")
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; "
            "padding: 5px 15px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #218838; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._save_btn.setEnabled(False)
        header_layout.addWidget(self._save_btn)
        
        layout.addLayout(header_layout)
        
        # Hinweis
        hint = QLabel(
            "💡 Hier kannst du den System-Prompt bearbeiten. "
            "Änderungen werden beim nächsten Anruf wirksam."
        )
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # Text Editor
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("AI-Instruktionen werden hier angezeigt...")
        self._text_edit.setStyleSheet(
            "QTextEdit { font-family: 'Consolas', 'Monaco', monospace; "
            "font-size: 12px; padding: 10px; }"
        )
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit, stretch=1)
        
        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._status_label)
    
    def _on_text_changed(self) -> None:
        """Handler für Textänderungen."""
        current_text = self._text_edit.toPlainText()
        has_changes = current_text != self._original_text
        
        self._save_btn.setEnabled(has_changes)
        self._reset_btn.setEnabled(has_changes)
        
        if has_changes:
            self._status_label.setText("⚠️ Ungespeicherte Änderungen")
            self._status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
        else:
            self._status_label.setText("")
    
    def _on_reset(self) -> None:
        """Setzt den Text auf den Original-Wert zurück."""
        self._text_edit.setPlainText(self._original_text)
        self._status_label.setText("↩️ Zurückgesetzt")
        self._status_label.setStyleSheet("color: #17a2b8; font-size: 11px;")
    
    def _on_save_clicked(self) -> None:
        """Speichert die Änderungen."""
        new_text = self._text_edit.toPlainText()
        
        if self._on_save:
            try:
                self._on_save(new_text)
                self._original_text = new_text
                self._save_btn.setEnabled(False)
                self._reset_btn.setEnabled(False)
                self._status_label.setText("✅ Gespeichert!")
                self._status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                self.instructions_changed.emit(new_text)
                logger.info("AI-Instruktionen aktualisiert")
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Fehler",
                    f"Konnte Instruktionen nicht speichern:\n{e}"
                )
        else:
            self._original_text = new_text
            self._save_btn.setEnabled(False)
            self._reset_btn.setEnabled(False)
            self._status_label.setText("✅ Gespeichert (lokal)")
            self._status_label.setStyleSheet("color: #28a745; font-size: 11px;")
    
    def set_instructions(self, text: str) -> None:
        """Setzt die aktuellen Instruktionen."""
        self._original_text = text
        self._text_edit.setPlainText(text)
        self._save_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)
        self._status_label.setText(f"📝 {len(text)} Zeichen")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
    
    def get_instructions(self) -> str:
        """Gibt die aktuellen Instruktionen zurück."""
        return self._text_edit.toPlainText()


# Demo/Test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    def on_save(text):
        print(f"Saved: {len(text)} chars")
    
    panel = InstructionsPanel(on_save=on_save)
    panel.setWindowTitle("AI Instruktionen")
    panel.resize(600, 500)
    
    panel.set_instructions("""Du bist ein freundlicher Assistent.
Hilf dem Benutzer bei seinen Fragen.
Sprich auf Deutsch.""")
    
    panel.show()
    sys.exit(app.exec())
