"""
Bestell Bot Voice - Remote GUI
==============================
Verbindet sich mit dem Server-Backend via REST API und WebSocket.
"""

import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QSplitter, QFrame, QStatusBar,
    QGroupBox, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QFont, QTextCursor, QColor

import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Server-Konfiguration
DEFAULT_SERVER_URL = "http://10.200.200.1:8085"
INSTRUCTIONS_FILE = Path(__file__).parent / "instructions.json"


class WebSocketWorker(QObject):
    """Worker für WebSocket-Verbindung in separatem Thread."""
    
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error = Signal(str)
    
    def __init__(self, server_url: str):
        super().__init__()
        self.server_url = server_url
        self._running = False
        self._ws = None
    
    async def _run_websocket(self):
        """Async WebSocket Loop."""
        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    self._ws = ws
                    self.connected.emit()
                    logger.info(f"WebSocket verbunden: {ws_url}")
                    
                    async for msg in ws:
                        if not self._running:
                            break
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                self.message_received.emit(data)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            self.error.emit(str(ws.exception()))
                            break
        
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._ws = None
            self.disconnected.emit()
    
    def run(self):
        """Startet den WebSocket-Loop."""
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_websocket())
        loop.close()
    
    def stop(self):
        """Stoppt die Verbindung."""
        self._running = False


class MainWindow(QMainWindow):
    """Hauptfenster der Remote-GUI."""
    
    def __init__(self, server_url: str = DEFAULT_SERVER_URL):
        super().__init__()
        self.server_url = server_url
        
        self._ws_worker: Optional[WebSocketWorker] = None
        self._ws_thread: Optional[QThread] = None
        
        self._connected = False
        self._sip_registered = False
        self._call_active = False
        self._caller_id = None
        
        self._transcript_text = ""
        self._current_partial = {"caller": "", "assistant": ""}
        self._original_instructions = ""
        self._original_model = ""
        self._available_models = []
        
        self._setup_ui()
        self._setup_timers()
        
        # Beim Start verbinden
        QTimer.singleShot(500, self._connect_to_server)
    
    def _setup_ui(self):
        """Erstellt das UI."""
        self.setWindowTitle("Bestell Bot Voice - Remote Control")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)
        
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Linke Seite: Status + Transkript
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # === Status Panel ===
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        # Verbindungs-Status
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(QLabel("API-Verbindung:"))
        self._api_status_label = QLabel("Nicht verbunden")
        self._api_status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self._api_status_label)
        conn_layout.addStretch()
        
        self._reconnect_btn = QPushButton("Verbinden")
        self._reconnect_btn.clicked.connect(self._connect_to_server)
        conn_layout.addWidget(self._reconnect_btn)
        status_layout.addLayout(conn_layout)
        
        # SIP-Status
        sip_layout = QHBoxLayout()
        sip_layout.addWidget(QLabel("SIP-Registrierung:"))
        self._sip_status_label = QLabel("Unbekannt")
        self._sip_status_label.setStyleSheet("color: gray;")
        sip_layout.addWidget(self._sip_status_label)
        sip_layout.addStretch()
        status_layout.addLayout(sip_layout)
        
        # Call-Status
        call_layout = QHBoxLayout()
        call_layout.addWidget(QLabel("Anruf:"))
        self._call_status_label = QLabel("Kein aktiver Anruf")
        self._call_status_label.setStyleSheet("color: gray;")
        call_layout.addWidget(self._call_status_label)
        call_layout.addStretch()
        
        self._hangup_btn = QPushButton("Auflegen")
        self._hangup_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 5px 15px; }"
        )
        self._hangup_btn.clicked.connect(self._on_hangup)
        self._hangup_btn.setEnabled(False)
        call_layout.addWidget(self._hangup_btn)
        
        self._mute_btn = QPushButton("AI Stumm")
        self._mute_btn.setCheckable(True)
        self._mute_btn.clicked.connect(self._on_mute_toggle)
        call_layout.addWidget(self._mute_btn)
        
        status_layout.addLayout(call_layout)
        
        status_group.setMaximumHeight(150)
        left_layout.addWidget(status_group)
        
        # === Transkript Panel ===
        transcript_group = QGroupBox("Live-Transkript")
        transcript_layout = QVBoxLayout(transcript_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._clear_btn = QPushButton("Löschen")
        self._clear_btn.clicked.connect(self._on_clear_transcript)
        btn_layout.addWidget(self._clear_btn)
        
        self._copy_btn = QPushButton("Kopieren")
        self._copy_btn.clicked.connect(self._on_copy_transcript)
        btn_layout.addWidget(self._copy_btn)
        
        transcript_layout.addLayout(btn_layout)
        
        # Text Area
        self._transcript_edit = QTextEdit()
        self._transcript_edit.setReadOnly(True)
        self._transcript_edit.setFont(QFont("Consolas", 11))
        self._transcript_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
            "border: 1px solid #3c3c3c; padding: 10px; }"
        )
        self._transcript_edit.setPlaceholderText(
            "Transkript erscheint hier, sobald ein Anruf aktiv ist..."
        )
        transcript_layout.addWidget(self._transcript_edit)
        
        left_layout.addWidget(transcript_group, stretch=1)
        
        main_layout.addWidget(left_widget, stretch=2)
        
        # Rechte Seite: Instructions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # === Model Panel ===
        model_group = QGroupBox("AI-Modell")
        model_layout = QVBoxLayout(model_group)
        
        # Hinweis
        model_hint = QLabel(
            "Wähle das OpenAI-Modell aus. "
            "Änderungen werden beim nächsten Anruf wirksam."
        )
        model_hint.setStyleSheet("color: #666; font-size: 11px;")
        model_hint.setWordWrap(True)
        model_layout.addWidget(model_hint)
        
        # Model Dropdown
        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(200)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        model_row.addWidget(self._model_combo)
        model_row.addStretch()
        
        self._model_status = QLabel("")
        self._model_status.setStyleSheet("color: #666; font-size: 11px;")
        model_row.addWidget(self._model_status)
        
        self._save_model_btn = QPushButton("Speichern")
        self._save_model_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 5px 15px; }"
        )
        self._save_model_btn.clicked.connect(self._on_save_model)
        self._save_model_btn.setEnabled(False)
        model_row.addWidget(self._save_model_btn)
        
        model_layout.addLayout(model_row)
        
        model_group.setMaximumHeight(100)
        right_layout.addWidget(model_group)
        
        # === Instructions Panel ===
        instructions_group = QGroupBox("AI-Instruktionen (System-Prompt)")
        instructions_layout = QVBoxLayout(instructions_group)
        
        # Hinweis
        hint = QLabel(
            "Hier kannst du den Kontext/System-Prompt bearbeiten. "
            "Änderungen werden beim nächsten Anruf wirksam."
        )
        hint.setStyleSheet("color: #666; font-size: 11px;")
        hint.setWordWrap(True)
        instructions_layout.addWidget(hint)
        
        # Text Editor
        self._instructions_edit = QTextEdit()
        self._instructions_edit.setFont(QFont("Consolas", 11))
        self._instructions_edit.setPlaceholderText("Lade Instruktionen vom Server...")
        self._instructions_edit.textChanged.connect(self._on_instructions_changed)
        instructions_layout.addWidget(self._instructions_edit, stretch=1)
        
        # Buttons
        btn_layout2 = QHBoxLayout()
        
        self._status_instructions = QLabel("")
        self._status_instructions.setStyleSheet("color: #666; font-size: 11px;")
        btn_layout2.addWidget(self._status_instructions)
        
        btn_layout2.addStretch()
        
        self._reset_btn = QPushButton("Zurücksetzen")
        self._reset_btn.clicked.connect(self._on_reset_instructions)
        self._reset_btn.setEnabled(False)
        btn_layout2.addWidget(self._reset_btn)
        
        self._save_btn = QPushButton("Speichern")
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 5px 15px; }"
        )
        self._save_btn.clicked.connect(self._on_save_instructions)
        self._save_btn.setEnabled(False)
        btn_layout2.addWidget(self._save_btn)
        
        instructions_layout.addLayout(btn_layout2)
        
        right_layout.addWidget(instructions_group)
        
        right_widget.setMinimumWidth(350)
        right_widget.setMaximumWidth(450)
        main_layout.addWidget(right_widget)
        
        # Status Bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Starte...")
    
    def _setup_timers(self):
        """Richtet Timer ein."""
        # Polling Timer für Status (falls WebSocket ausfällt)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_status)
        self._poll_timer.setInterval(5000)
    
    def _connect_to_server(self):
        """Verbindet zum Server via WebSocket."""
        # Alte Verbindung beenden
        if self._ws_thread and self._ws_thread.isRunning():
            self._ws_worker.stop()
            self._ws_thread.quit()
            self._ws_thread.wait(2000)
        
        # Neue Verbindung starten
        self._ws_worker = WebSocketWorker(self.server_url)
        self._ws_thread = QThread()
        self._ws_worker.moveToThread(self._ws_thread)
        
        self._ws_thread.started.connect(self._ws_worker.run)
        self._ws_worker.connected.connect(self._on_ws_connected)
        self._ws_worker.disconnected.connect(self._on_ws_disconnected)
        self._ws_worker.message_received.connect(self._on_ws_message)
        self._ws_worker.error.connect(self._on_ws_error)
        
        self._ws_thread.start()
        self._status_bar.showMessage("Verbinde zum Server...")
    
    def _on_ws_connected(self):
        """WebSocket verbunden."""
        self._connected = True
        self._api_status_label.setText("Verbunden")
        self._api_status_label.setStyleSheet("color: green; font-weight: bold;")
        self._reconnect_btn.setText("Neu verbinden")
        self._status_bar.showMessage(f"Mit {self.server_url} verbunden")
        
        # Model und Instructions laden
        self._load_model()
        self._load_instructions()
        
        # Polling stoppen (WebSocket ist besser)
        self._poll_timer.stop()
    
    def _on_ws_disconnected(self):
        """WebSocket getrennt."""
        self._connected = False
        self._api_status_label.setText("Getrennt")
        self._api_status_label.setStyleSheet("color: red; font-weight: bold;")
        self._reconnect_btn.setText("Verbinden")
        self._status_bar.showMessage("Verbindung verloren")
        
        # Polling starten als Fallback
        self._poll_timer.start()
    
    def _on_ws_error(self, error: str):
        """WebSocket Fehler."""
        logger.error(f"WebSocket Fehler: {error}")
        self._status_bar.showMessage(f"Fehler: {error}")
    
    def _on_ws_message(self, data: dict):
        """Verarbeitet WebSocket-Nachricht vom Server."""
        msg_type = data.get("type", "")
        
        if msg_type == "status":
            # Initial-Status
            self._sip_registered = data.get("sip_registered", False)
            self._call_active = data.get("call_active", False)
            self._update_status_display()
        
        elif msg_type == "call_incoming":
            self._caller_id = data.get("caller_id", "Unbekannt")
            self._call_status_label.setText(f"Eingehender Anruf: {self._caller_id}")
            self._call_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self._status_bar.showMessage(f"Eingehender Anruf von {self._caller_id}")
        
        elif msg_type == "call_active":
            self._call_active = True
            self._caller_id = data.get("caller_id", self._caller_id)
            self._hangup_btn.setEnabled(True)
            self._update_status_display()
            self._status_bar.showMessage(f"Anruf aktiv mit {self._caller_id}")
        
        elif msg_type == "call_ended":
            self._call_active = False
            self._caller_id = None
            self._hangup_btn.setEnabled(False)
            reason = data.get("reason", "")
            self._update_status_display()
            self._status_bar.showMessage(f"Anruf beendet: {reason}")
        
        elif msg_type == "transcript":
            self._on_transcript_update(
                data.get("role", ""),
                data.get("text", ""),
                data.get("is_final", False)
            )
    
    def _update_status_display(self):
        """Aktualisiert die Status-Anzeigen."""
        # SIP Status
        if self._sip_registered:
            self._sip_status_label.setText("Registriert")
            self._sip_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self._sip_status_label.setText("Nicht registriert")
            self._sip_status_label.setStyleSheet("color: red;")
        
        # Call Status
        if self._call_active:
            self._call_status_label.setText(f"Aktiv: {self._caller_id or 'Unbekannt'}")
            self._call_status_label.setStyleSheet("color: green; font-weight: bold;")
            self._hangup_btn.setEnabled(True)
        else:
            self._call_status_label.setText("Kein aktiver Anruf")
            self._call_status_label.setStyleSheet("color: gray;")
            self._hangup_btn.setEnabled(False)
    
    def _on_transcript_update(self, speaker: str, text: str, is_final: bool):
        """Verarbeitet Transkript-Updates."""
        if is_final:
            # Finalen Text hinzufügen
            speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
            self._transcript_text += f"[{speaker_label}] {text}\n"
            self._current_partial[speaker] = ""
        else:
            # Partial Update
            self._current_partial[speaker] = text
        
        self._update_transcript_display()
    
    def _update_transcript_display(self):
        """Aktualisiert die Transkript-Anzeige."""
        display_text = self._transcript_text
        
        # Partials anhängen
        for speaker, partial in self._current_partial.items():
            if partial:
                speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
                display_text += f"[{speaker_label}] {partial}...\n"
        
        self._transcript_edit.setPlainText(display_text)
        
        # Scroll nach unten
        cursor = self._transcript_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._transcript_edit.setTextCursor(cursor)
    
    def _on_clear_transcript(self):
        """Löscht das Transkript."""
        self._transcript_text = ""
        self._current_partial = {"caller": "", "assistant": ""}
        self._transcript_edit.clear()
    
    def _on_copy_transcript(self):
        """Kopiert das Transkript."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._transcript_text)
        self._status_bar.showMessage("Transkript kopiert")
    
    def _load_model(self):
        """Lädt Model vom Server."""
        import requests
        try:
            response = requests.get(f"{self.server_url}/model", timeout=5)
            if response.status_code == 200:
                data = response.json()
                current_model = data.get("model", "")
                available_models = data.get("available_models", [])
                
                self._original_model = current_model
                self._available_models = available_models
                
                # Dropdown befüllen
                self._model_combo.blockSignals(True)
                self._model_combo.clear()
                for model in available_models:
                    self._model_combo.addItem(model)
                
                # Aktuelles Model auswählen
                index = self._model_combo.findText(current_model)
                if index >= 0:
                    self._model_combo.setCurrentIndex(index)
                
                self._model_combo.blockSignals(False)
                self._model_status.setText("Geladen")
                self._model_status.setStyleSheet("color: #28a745; font-size: 11px;")
                self._save_model_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Fehler beim Laden des Models: {e}")
            self._model_status.setText("Fehler beim Laden")
            self._model_status.setStyleSheet("color: red; font-size: 11px;")
    
    def _on_model_changed(self, text: str):
        """Handler für Model-Änderungen."""
        has_changes = text != self._original_model
        self._save_model_btn.setEnabled(has_changes)
        
        if has_changes:
            self._model_status.setText("Ungespeichert")
            self._model_status.setStyleSheet("color: #ffc107; font-size: 11px;")
        else:
            self._model_status.setText("")
            self._model_status.setStyleSheet("color: #666; font-size: 11px;")
    
    def _on_save_model(self):
        """Speichert Model auf dem Server."""
        import requests
        
        model = self._model_combo.currentText()
        
        try:
            response = requests.post(
                f"{self.server_url}/model",
                json={"model": model},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    self._original_model = model
                    self._save_model_btn.setEnabled(False)
                    self._model_status.setText("Gespeichert!")
                    self._model_status.setStyleSheet("color: #28a745; font-size: 11px;")
                    self._status_bar.showMessage(f"Modell '{model}' gespeichert")
                else:
                    raise Exception(result.get("message", "Unbekannter Fehler"))
            else:
                raise Exception(f"Server-Fehler: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Models: {e}")
            QMessageBox.warning(self, "Fehler", f"Konnte nicht speichern: {e}")
    
    def _load_instructions(self):
        """Lädt Instructions vom Server."""
        import requests
        try:
            response = requests.get(f"{self.server_url}/instructions", timeout=5)
            if response.status_code == 200:
                data = response.json()
                instructions = data.get("instructions", "")
                self._original_instructions = instructions
                self._instructions_edit.setPlainText(instructions)
                self._status_instructions.setText(f"{len(instructions)} Zeichen")
                self._save_btn.setEnabled(False)
                self._reset_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Instructions: {e}")
            self._status_bar.showMessage(f"Fehler: {e}")
    
    def _on_instructions_changed(self):
        """Handler für Textänderungen."""
        current = self._instructions_edit.toPlainText()
        has_changes = current != self._original_instructions
        
        self._save_btn.setEnabled(has_changes)
        self._reset_btn.setEnabled(has_changes)
        
        if has_changes:
            self._status_instructions.setText("Ungespeicherte Änderungen")
            self._status_instructions.setStyleSheet("color: #ffc107; font-size: 11px;")
        else:
            self._status_instructions.setText(f"{len(current)} Zeichen")
            self._status_instructions.setStyleSheet("color: #666; font-size: 11px;")
    
    def _on_reset_instructions(self):
        """Setzt Instructions zurück."""
        self._instructions_edit.setPlainText(self._original_instructions)
    
    def _on_save_instructions(self):
        """Speichert Instructions auf dem Server."""
        import requests
        
        instructions = self._instructions_edit.toPlainText()
        
        try:
            response = requests.post(
                f"{self.server_url}/instructions",
                json={"instructions": instructions},
                timeout=5
            )
            
            if response.status_code == 200:
                self._original_instructions = instructions
                self._save_btn.setEnabled(False)
                self._reset_btn.setEnabled(False)
                self._status_instructions.setText("Gespeichert!")
                self._status_instructions.setStyleSheet("color: #28a745; font-size: 11px;")
                self._status_bar.showMessage("Instruktionen gespeichert")
                
                # Auch lokal speichern
                try:
                    with open(INSTRUCTIONS_FILE, "w", encoding="utf-8") as f:
                        json.dump({"instructions": instructions}, f, ensure_ascii=False, indent=2)
                except:
                    pass
            else:
                raise Exception(f"Server-Fehler: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")
            QMessageBox.warning(self, "Fehler", f"Konnte nicht speichern: {e}")
    
    def _on_hangup(self):
        """Beendet den Anruf."""
        import requests
        try:
            requests.post(f"{self.server_url}/call/hangup", timeout=5)
            self._status_bar.showMessage("Aufgelegt")
        except Exception as e:
            logger.error(f"Hangup Fehler: {e}")
    
    def _on_mute_toggle(self):
        """Schaltet AI stumm/an."""
        import requests
        try:
            if self._mute_btn.isChecked():
                requests.post(f"{self.server_url}/ai/mute", timeout=5)
                self._mute_btn.setText("AI Stumm (AN)")
                self._status_bar.showMessage("AI stummgeschaltet")
            else:
                requests.post(f"{self.server_url}/ai/unmute", timeout=5)
                self._mute_btn.setText("AI Stumm")
                self._status_bar.showMessage("AI aktiv")
        except Exception as e:
            logger.error(f"Mute Fehler: {e}")
    
    def _poll_status(self):
        """Pollt den Server-Status (Fallback wenn kein WebSocket)."""
        import requests
        try:
            response = requests.get(f"{self.server_url}/status", timeout=2)
            if response.status_code == 200:
                data = response.json()
                sip = data.get("sip", {})
                self._sip_registered = sip.get("registered", False)
                self._call_active = sip.get("in_call", False)
                self._caller_id = sip.get("caller_id")
                self._update_status_display()
                
                if not self._connected:
                    self._connected = True
                    self._api_status_label.setText("Verbunden (Polling)")
                    self._api_status_label.setStyleSheet("color: #ffc107; font-weight: bold;")
        except:
            self._connected = False
            self._api_status_label.setText("Nicht erreichbar")
            self._api_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def closeEvent(self, event):
        """Cleanup beim Schließen."""
        if self._ws_worker:
            self._ws_worker.stop()
        if self._ws_thread:
            self._ws_thread.quit()
            self._ws_thread.wait(2000)
        event.accept()


def main():
    """Startet die GUI-Anwendung."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bestell Bot Voice Remote GUI")
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER_URL,
        help=f"Server URL (default: {DEFAULT_SERVER_URL})"
    )
    
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Dark Theme
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(palette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(palette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(palette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(palette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(palette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(palette)
    
    window = MainWindow(server_url=args.server)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
