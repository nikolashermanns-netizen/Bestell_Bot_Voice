"""
Debug Panel für Entwickler-Informationen.
"""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.signals import AppSignals
from core.state import CallState


class DebugPanel(QWidget):
    """
    Panel für Debug-Informationen.

    Zeigt:
    - Call State
    - Latenz (RTT)
    - Audio Queue Größen
    - Letzter Fehler
    """

    def __init__(self, signals: AppSignals, parent: QWidget | None = None):
        super().__init__(parent)
        self._signals = signals
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Erstellt die UI-Elemente."""
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(20)

        # Style für Labels
        label_style = "font-size: 11px;"

        # Call State
        self._state_label = QLabel("State: IDLE")
        self._state_label.setStyleSheet(label_style + " color: gray;")
        layout.addWidget(self._state_label)

        # Separator
        layout.addWidget(self._create_separator())

        # Latency
        self._latency_label = QLabel("Latenz: --ms")
        self._latency_label.setStyleSheet(label_style)
        layout.addWidget(self._latency_label)

        # Separator
        layout.addWidget(self._create_separator())

        # Audio Queues
        self._queue_label = QLabel("Queue: 0/0")
        self._queue_label.setStyleSheet(label_style)
        layout.addWidget(self._queue_label)

        # Separator
        layout.addWidget(self._create_separator())

        # AI Status
        self._ai_label = QLabel("AI: --")
        self._ai_label.setStyleSheet(label_style)
        layout.addWidget(self._ai_label)

        layout.addStretch()

        # Error (rechtsbündig)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(label_style + " color: red;")
        layout.addWidget(self._error_label)

    def _create_separator(self) -> QFrame:
        """Erstellt einen vertikalen Separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    def _connect_signals(self) -> None:
        """Verbindet die Signals."""
        self._signals.call_state_changed.connect(self._on_call_state_changed)
        self._signals.debug_updated.connect(self._on_debug_updated)
        self._signals.error_occurred.connect(self._on_error_occurred)
        self._signals.ai_connection_changed.connect(self._on_ai_connection_changed)

    def _on_call_state_changed(self, state: CallState) -> None:
        """Handler für Call State Änderung."""
        state_colors = {
            CallState.IDLE: "gray",
            CallState.RINGING: "orange",
            CallState.ACTIVE: "green",
            CallState.ENDED: "gray",
        }
        color = state_colors.get(state, "gray")
        self._state_label.setText(f"State: {state.value.upper()}")
        self._state_label.setStyleSheet(f"font-size: 11px; color: {color};")

    def _on_debug_updated(self, info: dict) -> None:
        """Handler für Debug-Info Updates."""
        # Latenz
        latency = info.get("latency_ms", 0)
        latency_color = "green" if latency < 500 else "orange" if latency < 1000 else "red"
        self._latency_label.setText(f"Latenz: {latency:.0f}ms")
        self._latency_label.setStyleSheet(f"font-size: 11px; color: {latency_color};")

        # Queues
        in_queue = info.get("audio_in_queue", 0)
        out_queue = info.get("audio_out_queue", 0)
        self._queue_label.setText(f"Queue: {in_queue}/{out_queue}")

    def _on_error_occurred(self, error: str) -> None:
        """Handler für Fehler."""
        # Nur letzte 50 Zeichen anzeigen
        short_error = error[:50] + "..." if len(error) > 50 else error
        self._error_label.setText(short_error)
        self._error_label.setToolTip(error)

    def _on_ai_connection_changed(self, connected: bool) -> None:
        """Handler für AI Verbindungsstatus."""
        if connected:
            self._ai_label.setText("AI: Verbunden")
            self._ai_label.setStyleSheet("font-size: 11px; color: green;")
        else:
            self._ai_label.setText("AI: Getrennt")
            self._ai_label.setStyleSheet("font-size: 11px; color: gray;")

    def clear_error(self) -> None:
        """Löscht die Fehleranzeige."""
        self._error_label.setText("")
        self._error_label.setToolTip("")
