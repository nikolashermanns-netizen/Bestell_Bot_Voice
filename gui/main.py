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
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QSplitter, QFrame, QStatusBar,
    QGroupBox, QMessageBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSlider, QScrollArea, QTabWidget
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


class DebugWindow(QWidget):
    """Debug-Fenster für OpenAI Events."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenAI Debug Log")
        self.setMinimumSize(600, 400)
        self.resize(800, 500)
        
        layout = QVBoxLayout(self)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Löschen")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Log-Anzeige
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Consolas", 10))
        self._log_edit.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #00ff00; "
            "border: 1px solid #333; padding: 5px; font-family: Consolas; }"
        )
        layout.addWidget(self._log_edit)
    
    def add_event(self, entry: dict):
        """Fügt ein Event zum Log hinzu."""
        time = entry.get("time", "")
        event_type = entry.get("type", "")
        data = entry.get("data", {})
        
        # Farbe basierend auf Event-Typ
        if "error" in event_type.lower():
            color = "#ff4444"
        elif "function" in event_type.lower():
            color = "#44ff44"
        elif "transcript" in event_type.lower():
            color = "#4444ff"
        elif "response" in event_type.lower():
            color = "#ffff44"
        else:
            color = "#00ff00"
        
        # Formatierte Zeile
        data_str = ""
        if data:
            import json
            data_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        html = f'<span style="color: #888;">[{time}]</span> <span style="color: {color};">{event_type}</span>'
        if data_str:
            html += f'<pre style="color: #aaa; margin: 2px 0 10px 20px;">{data_str}</pre>'
        
        self._log_edit.append(html)
        
        # Scroll nach unten
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_edit.setTextCursor(cursor)
    
    def _on_clear(self):
        """Log löschen."""
        self._log_edit.clear()


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
        self._original_expert_instructions = ""
        self._original_model = ""
        self._available_models = []
        
        self._debug_log = []  # Debug-Events speichern
        self._debug_window = None  # Debug-Fenster
        
        # Experten-Konfiguration
        self._expert_models = {}  # {model_name: {info}}
        self._enabled_expert_models = []
        self._expert_checkboxes = {}  # {model_name: QCheckBox}
        self._expert_stats = {}
        
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
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Horizontaler Splitter für Links/Rechts
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(5)
        main_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: #555;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #777;
            }
        """)
        
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
        
        # Firewall Toggle
        sip_layout.addWidget(QLabel("Firewall:"))
        self._firewall_btn = QPushButton("Aktiv")
        self._firewall_btn.setCheckable(True)
        self._firewall_btn.setChecked(True)
        self._firewall_btn.setStyleSheet("""
            QPushButton { 
                background-color: #28a745; 
                color: white; 
                padding: 3px 10px; 
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:checked { 
                background-color: #28a745; 
            }
            QPushButton:!checked { 
                background-color: #dc3545; 
            }
        """)
        self._firewall_btn.clicked.connect(self._on_firewall_toggle)
        sip_layout.addWidget(self._firewall_btn)
        
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
        
        self._debug_btn = QPushButton("Debug Log")
        self._debug_btn.setCheckable(True)
        self._debug_btn.clicked.connect(self._on_toggle_debug)
        call_layout.addWidget(self._debug_btn)
        
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
        
        # === Orders Panel ===
        orders_group = QGroupBox("Aktuelle Bestellung")
        orders_layout = QVBoxLayout(orders_group)
        
        # Info-Zeile
        self._order_info_label = QLabel("Keine aktive Bestellung")
        self._order_info_label.setStyleSheet("color: #888;")
        orders_layout.addWidget(self._order_info_label)
        
        # Tabelle
        self._orders_table = QTableWidget()
        self._orders_table.setColumnCount(4)
        self._orders_table.setHorizontalHeaderLabels(["Menge", "Produkt", "Artikel Nr.", "Zeit"])
        self._orders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._orders_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._orders_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._orders_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._orders_table.setAlternatingRowColors(True)
        self._orders_table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; color: #d4d4d4; "
            "border: 1px solid #3c3c3c; }"
            "QTableWidget::item { padding: 5px; }"
            "QHeaderView::section { background-color: #2d2d2d; color: #d4d4d4; "
            "border: 1px solid #3c3c3c; padding: 5px; }"
        )
        self._orders_table.setMinimumHeight(120)
        orders_layout.addWidget(self._orders_table)
        
        # Splitter für Transkript und Orders
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.addWidget(transcript_group)
        left_splitter.addWidget(orders_group)
        left_splitter.setSizes([400, 200])  # 2:1 Verhältnis
        
        left_layout.addWidget(left_splitter, stretch=1)
        
        # Linke Seite zum Splitter hinzufügen
        main_splitter.addWidget(left_widget)
        
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
        
        # === Expert Models Panel ===
        expert_group = QGroupBox("Experten-Modelle (Kollege)")
        expert_layout = QVBoxLayout(expert_group)
        
        # Hinweis
        expert_hint = QLabel(
            "Konfiguriere welche Modelle der 'Kollege' für komplexe Fragen nutzen darf. "
            "Die AI wählt automatisch basierend auf Dringlichkeit."
        )
        expert_hint.setStyleSheet("color: #666; font-size: 11px;")
        expert_hint.setWordWrap(True)
        expert_layout.addWidget(expert_hint)
        
        # Modell-Checkboxen in ScrollArea
        expert_scroll = QScrollArea()
        expert_scroll.setWidgetResizable(True)
        expert_scroll.setMaximumHeight(120)
        expert_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        expert_models_widget = QWidget()
        expert_models_layout = QVBoxLayout(expert_models_widget)
        expert_models_layout.setContentsMargins(0, 0, 0, 0)
        expert_models_layout.setSpacing(2)
        
        # Platzhalter für Modell-Checkboxen (werden dynamisch geladen)
        self._expert_models_container = expert_models_layout
        self._expert_loading_label = QLabel("Lade Modelle vom Server...")
        self._expert_loading_label.setStyleSheet("color: #888; font-style: italic;")
        expert_models_layout.addWidget(self._expert_loading_label)
        
        expert_scroll.setWidget(expert_models_widget)
        expert_layout.addWidget(expert_scroll)
        
        # Konfidenz-Slider
        confidence_row = QHBoxLayout()
        confidence_row.addWidget(QLabel("Min. Konfidenz:"))
        
        self._confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._confidence_slider.setMinimum(50)
        self._confidence_slider.setMaximum(100)
        self._confidence_slider.setValue(90)
        self._confidence_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._confidence_slider.setTickInterval(10)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)
        confidence_row.addWidget(self._confidence_slider)
        
        self._confidence_label = QLabel("90%")
        self._confidence_label.setMinimumWidth(40)
        confidence_row.addWidget(self._confidence_label)
        
        expert_layout.addLayout(confidence_row)
        
        # Status und Speichern
        expert_btn_row = QHBoxLayout()
        
        self._expert_status_label = QLabel("")
        self._expert_status_label.setStyleSheet("color: #666; font-size: 11px;")
        expert_btn_row.addWidget(self._expert_status_label)
        
        expert_btn_row.addStretch()
        
        self._save_expert_btn = QPushButton("Speichern")
        self._save_expert_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 5px 15px; }"
        )
        self._save_expert_btn.clicked.connect(self._on_save_expert_config)
        self._save_expert_btn.setEnabled(False)
        expert_btn_row.addWidget(self._save_expert_btn)
        
        expert_layout.addLayout(expert_btn_row)
        
        # Experten-Anfrage Anzeige
        self._expert_query_label = QLabel("")
        self._expert_query_label.setStyleSheet(
            "color: #17a2b8; font-size: 11px; padding: 5px; "
            "background-color: #1a3a4a; border-radius: 3px;"
        )
        self._expert_query_label.setWordWrap(True)
        self._expert_query_label.setVisible(False)
        expert_layout.addWidget(self._expert_query_label)
        
        expert_group.setMaximumHeight(280)
        right_layout.addWidget(expert_group)
        
        # === Kontext Panel mit Tabs ===
        context_group = QGroupBox("Kontext / System-Prompts")
        context_layout = QVBoxLayout(context_group)
        
        # Tab Widget
        self._context_tabs = QTabWidget()
        self._context_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3c3c3c; }
            QTabBar::tab { 
                background-color: #2d2d2d; 
                color: #aaa; 
                padding: 8px 15px; 
                border: 1px solid #3c3c3c;
                border-bottom: none;
            }
            QTabBar::tab:selected { 
                background-color: #353535; 
                color: white; 
            }
        """)
        
        # === Tab 1: Sprach-AI ===
        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        voice_layout.setContentsMargins(5, 10, 5, 5)
        
        voice_hint = QLabel(
            "Kontext für die Sprach-AI (Telefonassistent). "
            "Änderungen werden beim nächsten Anruf wirksam."
        )
        voice_hint.setStyleSheet("color: #666; font-size: 11px;")
        voice_hint.setWordWrap(True)
        voice_layout.addWidget(voice_hint)
        
        self._instructions_edit = QTextEdit()
        self._instructions_edit.setFont(QFont("Consolas", 10))
        self._instructions_edit.setPlaceholderText("Lade Instruktionen vom Server...")
        self._instructions_edit.textChanged.connect(self._on_instructions_changed)
        voice_layout.addWidget(self._instructions_edit, stretch=1)
        
        voice_btn_layout = QHBoxLayout()
        self._status_instructions = QLabel("")
        self._status_instructions.setStyleSheet("color: #666; font-size: 11px;")
        voice_btn_layout.addWidget(self._status_instructions)
        voice_btn_layout.addStretch()
        
        self._reset_btn = QPushButton("Zurücksetzen")
        self._reset_btn.clicked.connect(self._on_reset_instructions)
        self._reset_btn.setEnabled(False)
        voice_btn_layout.addWidget(self._reset_btn)
        
        self._save_btn = QPushButton("Speichern")
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 5px 15px; }"
        )
        self._save_btn.clicked.connect(self._on_save_instructions)
        self._save_btn.setEnabled(False)
        voice_btn_layout.addWidget(self._save_btn)
        
        voice_layout.addLayout(voice_btn_layout)
        self._context_tabs.addTab(voice_tab, "Sprach-AI")
        
        # === Tab 2: Experten-AI ===
        expert_tab = QWidget()
        expert_layout2 = QVBoxLayout(expert_tab)
        expert_layout2.setContentsMargins(5, 10, 5, 5)
        
        expert_hint = QLabel(
            "Kontext für den Experten-Kollegen. Dieser beantwortet komplexe Fachfragen. "
            "WICHTIG: Antwort-Format muss JSON bleiben!"
        )
        expert_hint.setStyleSheet("color: #666; font-size: 11px;")
        expert_hint.setWordWrap(True)
        expert_layout2.addWidget(expert_hint)
        
        self._expert_instructions_edit = QTextEdit()
        self._expert_instructions_edit.setFont(QFont("Consolas", 10))
        self._expert_instructions_edit.setPlaceholderText("Lade Experten-Instruktionen vom Server...")
        self._expert_instructions_edit.textChanged.connect(self._on_expert_instructions_changed)
        expert_layout2.addWidget(self._expert_instructions_edit, stretch=1)
        
        expert_btn_layout = QHBoxLayout()
        self._status_expert_instructions = QLabel("")
        self._status_expert_instructions.setStyleSheet("color: #666; font-size: 11px;")
        expert_btn_layout.addWidget(self._status_expert_instructions)
        expert_btn_layout.addStretch()
        
        self._reset_expert_btn = QPushButton("Zurücksetzen")
        self._reset_expert_btn.clicked.connect(self._on_reset_expert_instructions)
        self._reset_expert_btn.setEnabled(False)
        expert_btn_layout.addWidget(self._reset_expert_btn)
        
        self._save_expert_instructions_btn = QPushButton("Speichern")
        self._save_expert_instructions_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 5px 15px; }"
        )
        self._save_expert_instructions_btn.clicked.connect(self._on_save_expert_instructions)
        self._save_expert_instructions_btn.setEnabled(False)
        expert_btn_layout.addWidget(self._save_expert_instructions_btn)
        
        expert_layout2.addLayout(expert_btn_layout)
        self._context_tabs.addTab(expert_tab, "Experten-AI")
        
        context_layout.addWidget(self._context_tabs)
        right_layout.addWidget(context_group)
        
        # Rechte Seite zum Splitter hinzufügen
        right_widget.setMinimumWidth(300)
        main_splitter.addWidget(right_widget)
        
        # Splitter zum Hauptlayout
        main_splitter.setSizes([700, 400])  # Startverhältnis ca. 2:1
        main_splitter.setCollapsible(0, False)  # Linke Seite nicht einklappbar
        main_splitter.setCollapsible(1, False)  # Rechte Seite nicht einklappbar
        main_layout.addWidget(main_splitter)
        
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
        
        # Model, Instructions und Expert-Config laden
        self._load_model()
        self._load_instructions()
        self._load_expert_instructions()
        self._load_expert_config()
        
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
            # Bestellungs-Tabelle leeren
            self._orders_table.setRowCount(0)
            self._order_info_label.setText("Keine aktive Bestellung")
            self._order_info_label.setStyleSheet("color: #888;")
        
        elif msg_type == "transcript":
            self._on_transcript_update(
                data.get("role", ""),
                data.get("text", ""),
                data.get("is_final", False)
            )
        
        elif msg_type == "order_update":
            self._on_order_update(data.get("order", {}))
        
        elif msg_type == "debug_event":
            self._on_debug_event(data.get("event", {}))
        
        elif msg_type == "expert_query_start":
            self._on_expert_query_start(
                data.get("question", ""),
                data.get("model", "")
            )
        
        elif msg_type == "expert_query_done":
            self._on_expert_query_done(data)
        
        elif msg_type == "firewall_status":
            self._update_firewall_button(data.get("enabled", True))
        
        elif msg_type == "call_rejected":
            # Anruf wurde wegen Firewall abgelehnt
            remote_ip = data.get("remote_ip", "?")
            caller_id = data.get("caller_id", "?")
            self._status_bar.showMessage(f"Anruf abgelehnt: {caller_id} (IP: {remote_ip})")
    
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
            # Finalen Text mit Zeitstempel hinzufügen
            time_str = datetime.now().strftime("%H:%M:%S")
            speaker_label = "Anrufer" if speaker == "caller" else "Assistent"
            self._transcript_text += f"[{time_str}] [{speaker_label}] {text}\n"
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
    
    def _on_order_update(self, order_data: dict):
        """Aktualisiert die Bestellungs-Anzeige."""
        items = order_data.get("items", [])
        caller_id = order_data.get("caller_id", "")
        total_qty = order_data.get("total_quantity", 0)
        
        # Info-Label aktualisieren
        if items:
            self._order_info_label.setText(
                f"Anrufer: {caller_id} | {len(items)} Positionen, {total_qty} Stück gesamt"
            )
            self._order_info_label.setStyleSheet("color: #28a745; font-weight: bold;")
        else:
            self._order_info_label.setText("Keine Positionen")
            self._order_info_label.setStyleSheet("color: #888;")
        
        # Tabelle aktualisieren
        self._orders_table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            menge = QTableWidgetItem(str(item.get("menge", 0)))
            menge.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            produktname = QTableWidgetItem(item.get("produktname", ""))
            kennung = QTableWidgetItem(item.get("kennung", ""))
            
            # Zeit formatieren
            timestamp = item.get("timestamp", "")
            if timestamp:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except:
                    time_str = timestamp[:8] if len(timestamp) >= 8 else timestamp
            else:
                time_str = ""
            zeit = QTableWidgetItem(time_str)
            
            self._orders_table.setItem(row, 0, menge)
            self._orders_table.setItem(row, 1, produktname)
            self._orders_table.setItem(row, 2, kennung)
            self._orders_table.setItem(row, 3, zeit)
    
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
                elif result.get("status") == "error":
                    # Server meldet Fehler beim persistenten Speichern
                    error_msg = result.get("message", "Unbekannter Fehler")
                    self._model_status.setText("Speicherfehler!")
                    self._model_status.setStyleSheet("color: #dc3545; font-size: 11px;")
                    QMessageBox.warning(self, "Speicherfehler", 
                        f"Das Modell wurde gesetzt, aber nicht persistent gespeichert:\n{error_msg}")
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
    
    def _load_expert_instructions(self):
        """Lädt Experten-Instruktionen vom Server."""
        import requests
        try:
            response = requests.get(f"{self.server_url}/expert/instructions", timeout=5)
            if response.status_code == 200:
                data = response.json()
                instructions = data.get("instructions", "")
                self._original_expert_instructions = instructions
                self._expert_instructions_edit.setPlainText(instructions)
                self._status_expert_instructions.setText(f"{len(instructions)} Zeichen")
                self._save_expert_instructions_btn.setEnabled(False)
                self._reset_expert_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Experten-Instructions: {e}")
    
    def _on_expert_instructions_changed(self):
        """Handler für Textänderungen bei Experten-Instruktionen."""
        current = self._expert_instructions_edit.toPlainText()
        has_changes = current != self._original_expert_instructions
        
        self._save_expert_instructions_btn.setEnabled(has_changes)
        self._reset_expert_btn.setEnabled(has_changes)
        
        if has_changes:
            self._status_expert_instructions.setText("Ungespeicherte Änderungen")
            self._status_expert_instructions.setStyleSheet("color: #ffc107; font-size: 11px;")
        else:
            self._status_expert_instructions.setText(f"{len(current)} Zeichen")
            self._status_expert_instructions.setStyleSheet("color: #666; font-size: 11px;")
    
    def _on_reset_expert_instructions(self):
        """Setzt Experten-Instructions zurück."""
        self._expert_instructions_edit.setPlainText(self._original_expert_instructions)
    
    def _on_save_expert_instructions(self):
        """Speichert Experten-Instructions auf dem Server."""
        import requests
        
        instructions = self._expert_instructions_edit.toPlainText()
        
        try:
            response = requests.post(
                f"{self.server_url}/expert/instructions",
                json={"instructions": instructions},
                timeout=5
            )
            
            if response.status_code == 200:
                self._original_expert_instructions = instructions
                self._save_expert_instructions_btn.setEnabled(False)
                self._reset_expert_btn.setEnabled(False)
                self._status_expert_instructions.setText("Gespeichert!")
                self._status_expert_instructions.setStyleSheet("color: #28a745; font-size: 11px;")
                self._status_bar.showMessage("Experten-Instruktionen gespeichert")
            else:
                raise Exception(f"Server-Fehler: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Experten-Instructions: {e}")
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
    
    def _on_firewall_toggle(self):
        """Schaltet SIP-Firewall an/aus."""
        import requests
        try:
            enabled = self._firewall_btn.isChecked()
            response = requests.post(
                f"{self.server_url}/firewall",
                json={"enabled": enabled},
                timeout=5
            )
            if response.status_code == 200:
                self._update_firewall_button(enabled)
                status = "aktiviert" if enabled else "DEAKTIVIERT"
                self._status_bar.showMessage(f"SIP-Firewall {status}")
            else:
                # Fehler - Button zurücksetzen
                self._firewall_btn.setChecked(not enabled)
        except Exception as e:
            logger.error(f"Firewall Toggle Fehler: {e}")
            # Button zurücksetzen bei Fehler
            self._firewall_btn.setChecked(not self._firewall_btn.isChecked())
    
    def _update_firewall_button(self, enabled: bool):
        """Aktualisiert den Firewall-Button-Status."""
        self._firewall_btn.setChecked(enabled)
        if enabled:
            self._firewall_btn.setText("Aktiv")
        else:
            self._firewall_btn.setText("AUS!")
    
    def _on_toggle_debug(self):
        """Debug-Log Fenster ein/ausblenden."""
        if self._debug_btn.isChecked():
            if self._debug_window is None:
                self._debug_window = DebugWindow(self)
            self._debug_window.show()
            # Bestehende Logs anzeigen
            for entry in self._debug_log[-100:]:  # Letzte 100
                self._debug_window.add_event(entry)
        else:
            if self._debug_window:
                self._debug_window.hide()
    
    def _on_debug_event(self, event: dict):
        """Debug-Event von Server empfangen."""
        from datetime import datetime
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": event.get("type", "unknown"),
            "data": event.get("data", {})
        }
        self._debug_log.append(entry)
        
        # An Debug-Fenster senden wenn offen
        if self._debug_window and self._debug_window.isVisible():
            self._debug_window.add_event(entry)
    
    def _load_expert_config(self):
        """Lädt Experten-Konfiguration vom Server."""
        import requests
        try:
            response = requests.get(f"{self.server_url}/expert/config", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                self._expert_models = data.get("available_models", {})
                self._enabled_expert_models = data.get("enabled_models", [])
                min_confidence = data.get("min_confidence", 0.9)
                
                # Slider aktualisieren
                self._confidence_slider.blockSignals(True)
                self._confidence_slider.setValue(int(min_confidence * 100))
                self._confidence_slider.blockSignals(False)
                self._confidence_label.setText(f"{int(min_confidence * 100)}%")
                
                # Lade-Label entfernen
                if self._expert_loading_label:
                    self._expert_loading_label.setVisible(False)
                
                # Checkboxen erstellen
                self._create_expert_checkboxes()
                
                self._expert_status_label.setText(f"{len(self._enabled_expert_models)} aktiv")
                self._expert_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                self._save_expert_btn.setEnabled(False)
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Expert-Config: {e}")
            self._expert_status_label.setText("Fehler beim Laden")
            self._expert_status_label.setStyleSheet("color: red; font-size: 11px;")
    
    def _create_expert_checkboxes(self):
        """Erstellt Checkboxen für alle Experten-Modelle."""
        # Alte Checkboxen entfernen
        for checkbox in self._expert_checkboxes.values():
            checkbox.setParent(None)
        self._expert_checkboxes.clear()
        
        # Neue Checkboxen erstellen
        for model_name, model_info in sorted(self._expert_models.items()):
            base = model_info.get("base", "?")
            speed = model_info.get("speed", "?")
            latency = model_info.get("latency_sec", "?")
            model_type = model_info.get("type", "standard")
            
            # Label mit Infos
            type_icon = "🧠" if model_type == "reasoning" else "⚡"
            label = f"{type_icon} {model_name} ({base}, ~{latency}s)"
            
            checkbox = QCheckBox(label)
            checkbox.setChecked(model_name in self._enabled_expert_models)
            checkbox.stateChanged.connect(self._on_expert_checkbox_changed)
            checkbox.setStyleSheet("font-size: 11px;")
            
            self._expert_checkboxes[model_name] = checkbox
            self._expert_models_container.addWidget(checkbox)
    
    def _on_expert_checkbox_changed(self):
        """Handler wenn eine Checkbox geändert wird."""
        self._save_expert_btn.setEnabled(True)
        self._expert_status_label.setText("Ungespeichert")
        self._expert_status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
    
    def _on_confidence_changed(self, value: int):
        """Handler für Konfidenz-Slider."""
        self._confidence_label.setText(f"{value}%")
        self._save_expert_btn.setEnabled(True)
        self._expert_status_label.setText("Ungespeichert")
        self._expert_status_label.setStyleSheet("color: #ffc107; font-size: 11px;")
    
    def _on_save_expert_config(self):
        """Speichert Experten-Konfiguration auf dem Server."""
        import requests
        
        # Aktivierte Modelle sammeln
        enabled_models = [
            model for model, checkbox in self._expert_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        min_confidence = self._confidence_slider.value() / 100.0
        
        try:
            response = requests.post(
                f"{self.server_url}/expert/config",
                json={
                    "enabled_models": enabled_models,
                    "min_confidence": min_confidence
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "ok":
                    self._enabled_expert_models = enabled_models
                    self._save_expert_btn.setEnabled(False)
                    self._expert_status_label.setText(f"Gespeichert! ({len(enabled_models)} aktiv)")
                    self._expert_status_label.setStyleSheet("color: #28a745; font-size: 11px;")
                    self._status_bar.showMessage("Experten-Konfiguration gespeichert")
                elif result.get("status") == "error":
                    # Server meldet Fehler beim persistenten Speichern
                    error_msg = result.get("message", "Unbekannter Fehler")
                    self._expert_status_label.setText("Speicherfehler!")
                    self._expert_status_label.setStyleSheet("color: #dc3545; font-size: 11px;")
                    QMessageBox.warning(self, "Speicherfehler", 
                        f"Die Konfiguration wurde gesetzt, aber nicht persistent gespeichert:\n{error_msg}")
            else:
                raise Exception(f"Server-Fehler: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Expert-Config: {e}")
            QMessageBox.warning(self, "Fehler", f"Konnte nicht speichern: {e}")
    
    def _on_expert_query_start(self, question: str, model: str):
        """Zeigt an, dass eine Experten-Anfrage läuft."""
        self._expert_query_label.setText(f"🔍 Frage Kollegen ({model}): {question[:80]}...")
        self._expert_query_label.setVisible(True)
        self._status_bar.showMessage(f"Experten-Anfrage an {model}...")
        
        # Ins Transkript einfügen
        time_str = datetime.now().strftime("%H:%M:%S")
        self._transcript_text += f"\n[{time_str}] [EXPERTE] Frage an {model}: {question}\n"
        self._update_transcript_display()
    
    def _on_expert_query_done(self, data: dict):
        """Zeigt das Ergebnis einer Experten-Anfrage."""
        success = data.get("success", False)
        model = data.get("model", "?")
        model_base = data.get("model_base", "?")
        confidence = data.get("confidence", 0)
        latency_ms = data.get("latency_ms", 0)
        answer = data.get("answer", "")
        
        if success:
            icon = "✅"
            color = "#28a745"
            msg = f"Antwort von {model} ({confidence:.0%} Konfidenz, {latency_ms}ms)"
        else:
            icon = "⚠️"
            color = "#ffc107"
            msg = f"Keine sichere Antwort ({confidence:.0%} < Minimum)"
        
        self._expert_query_label.setText(f"{icon} {msg}")
        self._expert_query_label.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 5px; "
            "background-color: #1a3a4a; border-radius: 3px;"
        )
        self._status_bar.showMessage(msg)
        
        # Ins Transkript einfügen
        time_str = datetime.now().strftime("%H:%M:%S")
        if success and answer:
            self._transcript_text += f"[{time_str}] [EXPERTE] Antwort ({confidence:.0%}): {answer}\n\n"
        else:
            self._transcript_text += f"[{time_str}] [EXPERTE] Keine sichere Antwort ({confidence:.0%})\n\n"
        self._update_transcript_display()
        
        # Nach 5 Sekunden ausblenden
        QTimer.singleShot(5000, lambda: self._expert_query_label.setVisible(False))

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
                
                # Firewall Status
                firewall = data.get("firewall", {})
                firewall_enabled = firewall.get("enabled", True)
                self._update_firewall_button(firewall_enabled)
                
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
