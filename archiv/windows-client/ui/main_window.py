"""
Hauptfenster der Bestell Bot Voice Anwendung.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStatusBar,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent

from config import AppConfig
from core.state import AppState, CallState
from core.signals import AppSignals, get_signals
from ui.call_panel import CallPanel
from ui.transcript_panel import TranscriptPanel
from ui.debug_panel import DebugPanel
from ui.audio_test_panel import AudioTestPanel
from ui.order_panel import OrderPanel
from ui.instructions_panel import InstructionsPanel

logger = logging.getLogger(__name__)

# Pfad für persistierte Instructions
INSTRUCTIONS_FILE = Path(__file__).parent.parent / "instructions.json"


class MainWindow(QMainWindow):
    """
    Hauptfenster der Anwendung.

    Layout:
    - Oben: Call Panel (Status, Controls)
    - Mitte: Transcript Panel (Live-Transkription)
    - Unten: Debug Panel (Latenz, Queues, Fehler)
    """

    def __init__(
        self,
        config: AppConfig,
        app_state: AppState,
        controller: Optional["CallController"] = None,
    ):
        super().__init__()
        self._config = config
        self._app_state = app_state
        self._controller = controller
        self._signals = get_signals()

        self._setup_ui()
        self._connect_signals()
        self._setup_timers()

        # Initial state
        self._update_from_state()

        # Test-Anruf Verfügbarkeit prüfen
        self._update_local_test_availability()

        # Auto-Accept Status anzeigen
        self._call_panel.set_auto_accept_enabled(config.auto_accept_calls)
        
        # Aktuelles AI-Model setzen
        if self._controller:
            self._call_panel.set_current_model(self._controller.get_ai_model())
        
        # AI-Instruktionen laden
        self._load_instructions()

    def _setup_ui(self) -> None:
        """Erstellt das UI-Layout."""
        self.setWindowTitle("Bestell Bot Voice - POC")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)

        # Zentrales Widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Haupt-Layout mit Tabs
        main_layout = QHBoxLayout()

        # Linke Seite: Call + Transcript
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter für Call und Transcript/Order Panels
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Call Panel (oben) mit Test-Anruf Callback
        self._call_panel = CallPanel(
            self._signals,
            on_start_local_test=self._on_start_local_test,
        )
        self._call_panel.setMinimumHeight(180)
        self._call_panel.setMaximumHeight(350)  # Erhöht für Codec-Buttons + Replay
        self._call_panel.set_codec_callback(self._on_codec_changed)
        self._call_panel.set_replay_callback(self._on_replay_audio)
        splitter.addWidget(self._call_panel)

        # Horizontaler Splitter für Transcript und Order
        transcript_order_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Transcript Panel (links)
        self._transcript_panel = TranscriptPanel(self._signals)
        transcript_order_splitter.addWidget(self._transcript_panel)
        
        # Order Panel (rechts neben Transcript)
        self._order_panel = OrderPanel()
        self._order_panel.setMinimumWidth(250)
        transcript_order_splitter.addWidget(self._order_panel)
        
        # Verhältnis Transcript:Order = 60:40
        transcript_order_splitter.setSizes([350, 250])
        
        splitter.addWidget(transcript_order_splitter)

        # Splitter-Verhältnis setzen (Call:Transcript+Order)
        splitter.setSizes([200, 450])

        left_layout.addWidget(splitter, stretch=1)

        main_layout.addWidget(left_widget, stretch=2)

        # Rechte Seite: Audio Test + Instructions Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(10)

        # Audio Test Panel
        self._audio_test_panel = AudioTestPanel()
        self._audio_test_panel.setMaximumHeight(350)
        right_layout.addWidget(self._audio_test_panel)
        
        # Instructions Panel (mit Save-Callback)
        self._instructions_panel = InstructionsPanel(
            on_save=self._on_save_instructions
        )
        right_layout.addWidget(self._instructions_panel, stretch=1)

        right_widget.setMaximumWidth(400)
        right_widget.setMinimumWidth(350)
        main_layout.addWidget(right_widget)

        layout.addLayout(main_layout, stretch=1)

        # Debug Panel (unten)
        self._debug_panel = DebugPanel(self._signals)
        self._debug_panel.setStyleSheet(
            "background-color: #2d2d2d; border-top: 1px solid #3c3c3c;"
        )
        layout.addWidget(self._debug_panel)

        # Status Bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Bereit")

    def _connect_signals(self) -> None:
        """Verbindet interne Signals."""
        # UI Actions an Backend weiterleiten
        self._signals.action_accept_call.connect(self._on_accept_call)
        self._signals.action_reject_call.connect(self._on_reject_call)
        self._signals.action_hangup.connect(self._on_hangup)
        self._signals.action_mute_ai.connect(self._on_mute_ai)

        # State Changes
        self._signals.call_state_changed.connect(self._on_call_state_changed)
        
        # Transkript-Updates an Order Panel weiterleiten
        self._signals.transcript_updated.connect(self._order_panel.on_transcript_update)

    def _setup_timers(self) -> None:
        """Richtet Timer für periodische Updates ein."""
        # Timer für Call-Dauer Update
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.setInterval(1000)

        # Timer für Debug-Info Update
        self._debug_timer = QTimer(self)
        self._debug_timer.timeout.connect(self._update_debug_info)
        self._debug_timer.setInterval(500)
        self._debug_timer.start()

    def _update_from_state(self) -> None:
        """Aktualisiert UI aus dem aktuellen State."""
        self._signals.call_state_changed.emit(self._app_state.call_state)
        self._signals.sip_registration_changed.emit(
            self._app_state.registration_state,
            self._app_state.registration_error,
        )

    def _on_accept_call(self) -> None:
        """Handler für Anruf annehmen."""
        if self._controller:
            self._controller.accept_call()
        else:
            # Fallback für Tests ohne Controller
            self._app_state.accept_call()
            self._signals.call_state_changed.emit(CallState.ACTIVE)
        self._status_bar.showMessage("Anruf angenommen")

    def _on_reject_call(self) -> None:
        """Handler für Anruf ablehnen."""
        if self._controller:
            self._controller.reject_call()
        else:
            self._app_state.end_call()
            self._signals.call_state_changed.emit(CallState.ENDED)
        self._status_bar.showMessage("Anruf abgelehnt")

    def _on_hangup(self) -> None:
        """Handler für Auflegen."""
        if self._controller:
            self._controller.hangup()
        else:
            self._app_state.end_call()
            self._signals.call_state_changed.emit(CallState.ENDED)
        self._status_bar.showMessage("Anruf beendet")

    def _on_mute_ai(self, muted: bool) -> None:
        """Handler für AI stumm schalten."""
        if self._controller:
            self._controller.set_ai_muted(muted)
        else:
            self._app_state.ai_muted = muted
            self._signals.ai_mute_changed.emit(muted)
        status = "AI stummgeschaltet" if muted else "AI aktiv"
        self._status_bar.showMessage(status)

    def _on_codec_changed(self, codec: str, sample_rate: int = 8000, bit_depth: int = 8) -> None:
        """Handler für Output-Einstellungen Änderung."""
        if self._controller and hasattr(self._controller, '_sip_client'):
            self._controller._sip_client.set_output_settings(codec, sample_rate, bit_depth)
            # Im Test-Modus: Audio neu vorbereiten mit neuen Einstellungen
            if self._controller._sip_client._test_mode:
                self._controller._sip_client.restart_test_audio()
            self._status_bar.showMessage(f"Output: {codec}, {sample_rate//1000}kHz, {bit_depth}-bit")
    
    def _on_replay_audio(self) -> None:
        """Handler für Replay-Button - startet Test-Audio von vorne."""
        if self._controller and hasattr(self._controller, '_sip_client'):
            self._controller._sip_client.restart_test_audio()
            self._status_bar.showMessage("Test-Audio wird neu gestartet...")

    def _on_start_local_test(self) -> None:
        """Handler für Test-Anruf starten."""
        if self._controller and self._controller.local_audio_available:
            # Ausgewählte Geräte aus Audio-Test Panel holen
            input_device, output_device = self._audio_test_panel.get_selected_devices()
            
            success = self._controller.start_local_call(
                input_device=input_device,
                output_device=output_device,
            )
            if success:
                self._status_bar.showMessage("Test-Anruf gestartet - sprich ins Mikrofon!")
            else:
                self._status_bar.showMessage("Fehler beim Starten des Test-Anrufs")
        else:
            self._status_bar.showMessage("Lokales Audio nicht verfügbar")

    def _update_local_test_availability(self) -> None:
        """Aktualisiert die Verfügbarkeit des Test-Anrufs."""
        if self._controller:
            available = self._controller.local_audio_available
            self._call_panel.set_local_test_available(available)
        else:
            self._call_panel.set_local_test_available(False)

    def _load_instructions(self) -> None:
        """Lädt die AI-Instruktionen aus der Datei oder vom Controller."""
        instructions = None
        
        # Zuerst versuchen, aus Datei zu laden
        if INSTRUCTIONS_FILE.exists():
            try:
                with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    instructions = data.get("instructions", "")
                    logger.info(f"Instructions aus {INSTRUCTIONS_FILE} geladen")
            except Exception as e:
                logger.warning(f"Fehler beim Laden der Instructions: {e}")
        
        # Falls keine gespeicherten Instructions, vom Controller holen (Default)
        if not instructions and self._controller:
            instructions = self._controller.get_ai_instructions()
        elif not instructions:
            instructions = "Kein Controller verfügbar - Instruktionen können nicht geladen werden."
        
        # Instructions im Panel setzen
        self._instructions_panel.set_instructions(instructions)
        
        # Falls aus Datei geladen, auch an Controller/API senden
        if self._controller and INSTRUCTIONS_FILE.exists():
            if hasattr(self._controller, '_realtime_client'):
                self._controller._realtime_client.set_instructions(instructions)

    def _on_save_instructions(self, text: str) -> None:
        """Speichert geänderte AI-Instruktionen in Datei und an API."""
        try:
            # In Datei speichern für Persistenz
            with open(INSTRUCTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({"instructions": text}, f, ensure_ascii=False, indent=2)
            logger.info(f"Instructions in {INSTRUCTIONS_FILE} gespeichert")
            
            # An API senden (falls verbunden)
            if self._controller and hasattr(self._controller, '_realtime_client'):
                self._controller._realtime_client.set_instructions(text)
            
            self._status_bar.showMessage("AI-Instruktionen gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Instructions: {e}")
            self._status_bar.showMessage(f"Fehler beim Speichern: {e}")

    def _on_call_state_changed(self, state: CallState) -> None:
        """Handler für Call State Änderungen."""
        if state == CallState.ACTIVE:
            self._duration_timer.start()
        else:
            self._duration_timer.stop()

    def _update_duration(self) -> None:
        """Aktualisiert die Anrufdauer-Anzeige."""
        duration = self._app_state.call_info.duration_seconds
        self._call_panel.update_duration(duration)

    def _update_debug_info(self) -> None:
        """Aktualisiert die Debug-Informationen."""
        info = {
            "latency_ms": self._app_state.debug.latency_ms,
            "audio_in_queue": self._app_state.debug.audio_in_queue_size,
            "audio_out_queue": self._app_state.debug.audio_out_queue_size,
        }
        self._signals.debug_updated.emit(info)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handler für Fenster schließen."""
        self.cleanup()
        event.accept()

    def cleanup(self) -> None:
        """Räumt Ressourcen auf."""
        self._duration_timer.stop()
        self._debug_timer.stop()

        # Controller wird über main.py aufgeräumt

    # === Öffentliche Methoden für Tests und Mock-Daten ===



# Demo/Test - nur mit echten Credentials möglich
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from core.signals import init_signals
    from config import load_config

    app = QApplication(sys.argv)

    # Signals initialisieren
    init_signals()

    # Echte Config laden
    try:
        config = load_config()
    except ValueError as e:
        print(f"Konfigurationsfehler: {e}")
        print("Bitte .env Datei mit echten Credentials erstellen.")
        sys.exit(1)

    state = AppState()

    window = MainWindow(config, state)
    window.show()

    sys.exit(app.exec())
