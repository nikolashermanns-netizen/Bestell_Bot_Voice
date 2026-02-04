"""
Call Control Panel für Anruf-Steuerung.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.state import CallState, RegistrationState
from core.signals import AppSignals


class LocalTestSignal:
    """Signal für lokalen Test-Anruf."""
    pass


class CallPanel(QWidget):
    """
    Panel für Call-Controls und Status-Anzeige.

    Zeigt:
    - SIP Registrierungsstatus
    - Eingehender Anruf mit Caller-ID
    - Accept/Reject/Hangup Buttons
    - Mute AI Toggle
    - Test-Anruf Button (lokales Mikrofon)
    """

    def __init__(
        self,
        signals: AppSignals,
        parent: QWidget | None = None,
        on_start_local_test: callable = None,
    ):
        super().__init__(parent)
        self._signals = signals
        self._current_call_state = CallState.IDLE
        self._on_start_local_test = on_start_local_test
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # === SIP Status ===
        sip_frame = QFrame()
        sip_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        sip_layout = QHBoxLayout(sip_frame)

        sip_label = QLabel("SIP Status:")
        sip_label.setFont(QFont("", -1, QFont.Weight.Bold))
        sip_layout.addWidget(sip_label)

        self._sip_status = QLabel("Nicht verbunden")
        self._sip_status.setStyleSheet("color: gray;")
        sip_layout.addWidget(self._sip_status)
        sip_layout.addStretch()

        # Auto-Accept Status
        self._auto_accept_label = QLabel("")
        self._auto_accept_label.setStyleSheet(
            "background-color: #17a2b8; color: white; "
            "padding: 3px 8px; border-radius: 3px; font-size: 11px;"
        )
        sip_layout.addWidget(self._auto_accept_label)
        self._auto_accept_label.hide()

        layout.addWidget(sip_frame)

        # === Incoming Call Info ===
        self._call_frame = QFrame()
        self._call_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._call_frame.setStyleSheet("background-color: #fff3cd; border-radius: 5px;")
        call_layout = QVBoxLayout(self._call_frame)

        self._call_label = QLabel("Eingehender Anruf")
        self._call_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self._call_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_layout.addWidget(self._call_label)

        self._caller_id_label = QLabel("")
        self._caller_id_label.setFont(QFont("", 14))
        self._caller_id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        call_layout.addWidget(self._caller_id_label)

        # Accept/Reject Buttons
        button_layout = QHBoxLayout()

        self._accept_btn = QPushButton("Annehmen")
        self._accept_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #218838; }"
        )
        self._accept_btn.clicked.connect(self._on_accept_clicked)
        button_layout.addWidget(self._accept_btn)

        self._reject_btn = QPushButton("Ablehnen")
        self._reject_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #c82333; }"
        )
        self._reject_btn.clicked.connect(self._on_reject_clicked)
        button_layout.addWidget(self._reject_btn)

        call_layout.addLayout(button_layout)
        layout.addWidget(self._call_frame)
        self._call_frame.hide()

        # === Active Call Controls ===
        self._active_frame = QFrame()
        self._active_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self._active_frame.setStyleSheet("background-color: #d4edda; border-radius: 5px;")
        active_layout = QVBoxLayout(self._active_frame)

        self._active_label = QLabel("Anruf aktiv")
        self._active_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self._active_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._active_label.setStyleSheet("color: #155724;")
        active_layout.addWidget(self._active_label)

        self._duration_label = QLabel("00:00")
        self._duration_label.setFont(QFont("", 16))
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        active_layout.addWidget(self._duration_label)

        # Hangup und Mute Buttons
        active_btn_layout = QHBoxLayout()

        self._hangup_btn = QPushButton("Auflegen")
        self._hangup_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #c82333; }"
        )
        self._hangup_btn.clicked.connect(self._on_hangup_clicked)
        active_btn_layout.addWidget(self._hangup_btn)

        self._mute_btn = QPushButton("AI Stumm")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #5a6268; }"
            "QPushButton:checked { background-color: #ffc107; color: black; }"
        )
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        active_btn_layout.addWidget(self._mute_btn)

        active_layout.addLayout(active_btn_layout)
        
        # === Output Audio Einstellungen (AI → Caller) ===
        output_frame = QFrame()
        output_frame.setStyleSheet("background-color: #e9ecef; border-radius: 3px;")
        output_layout = QVBoxLayout(output_frame)
        output_layout.setContentsMargins(5, 5, 5, 5)
        output_layout.setSpacing(3)
        
        output_title = QLabel("🔊 Output (AI → Telefon)")
        output_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #333;")
        output_layout.addWidget(output_title)
        
        # Zeile 1: Codec
        codec_row = QHBoxLayout()
        codec_label = QLabel("Codec:")
        codec_label.setStyleSheet("font-size: 10px; color: #333; min-width: 50px;")
        codec_row.addWidget(codec_label)
        
        self._codec_pcm8_btn = QPushButton("PCM8")
        self._codec_pcm8_btn.setCheckable(True)
        self._codec_pcm8_btn.setStyleSheet(self._codec_btn_style())
        self._codec_pcm8_btn.clicked.connect(lambda: self._on_codec_clicked("pcm8"))
        codec_row.addWidget(self._codec_pcm8_btn)
        
        self._codec_ulaw_btn = QPushButton("μ-law")
        self._codec_ulaw_btn.setCheckable(True)
        self._codec_ulaw_btn.setStyleSheet(self._codec_btn_style())
        self._codec_ulaw_btn.clicked.connect(lambda: self._on_codec_clicked("ulaw"))
        codec_row.addWidget(self._codec_ulaw_btn)
        
        # A-law ist der Default (von SDP: preference=PCMA)
        self._codec_alaw_btn = QPushButton("A-law ✓")
        self._codec_alaw_btn.setCheckable(True)
        self._codec_alaw_btn.setChecked(True)
        self._codec_alaw_btn.setStyleSheet(self._codec_btn_style())
        self._codec_alaw_btn.clicked.connect(lambda: self._on_codec_clicked("alaw"))
        codec_row.addWidget(self._codec_alaw_btn)
        
        codec_row.addStretch()
        output_layout.addLayout(codec_row)
        
        # Zeile 2: Sample Rate
        rate_row = QHBoxLayout()
        rate_label = QLabel("Rate:")
        rate_label.setStyleSheet("font-size: 10px; color: #333; min-width: 50px;")
        rate_row.addWidget(rate_label)
        
        self._rate_8k_btn = QPushButton("8kHz")
        self._rate_8k_btn.setCheckable(True)
        self._rate_8k_btn.setChecked(True)
        self._rate_8k_btn.setStyleSheet(self._codec_btn_style())
        self._rate_8k_btn.clicked.connect(lambda: self._on_rate_clicked(8000))
        rate_row.addWidget(self._rate_8k_btn)
        
        self._rate_16k_btn = QPushButton("16kHz")
        self._rate_16k_btn.setCheckable(True)
        self._rate_16k_btn.setStyleSheet(self._codec_btn_style())
        self._rate_16k_btn.clicked.connect(lambda: self._on_rate_clicked(16000))
        rate_row.addWidget(self._rate_16k_btn)
        
        self._rate_24k_btn = QPushButton("24kHz")
        self._rate_24k_btn.setCheckable(True)
        self._rate_24k_btn.setStyleSheet(self._codec_btn_style())
        self._rate_24k_btn.clicked.connect(lambda: self._on_rate_clicked(24000))
        rate_row.addWidget(self._rate_24k_btn)
        
        rate_row.addStretch()
        output_layout.addLayout(rate_row)
        
        # Zeile 3: Bit Depth
        bits_row = QHBoxLayout()
        bits_label = QLabel("Bits:")
        bits_label.setStyleSheet("font-size: 10px; color: #333; min-width: 50px;")
        bits_row.addWidget(bits_label)
        
        self._bits_8_btn = QPushButton("8-bit")
        self._bits_8_btn.setCheckable(True)
        self._bits_8_btn.setChecked(True)
        self._bits_8_btn.setStyleSheet(self._codec_btn_style())
        self._bits_8_btn.clicked.connect(lambda: self._on_bits_clicked(8))
        bits_row.addWidget(self._bits_8_btn)
        
        self._bits_16_btn = QPushButton("16-bit")
        self._bits_16_btn.setCheckable(True)
        self._bits_16_btn.setStyleSheet(self._codec_btn_style())
        self._bits_16_btn.clicked.connect(lambda: self._on_bits_clicked(16))
        bits_row.addWidget(self._bits_16_btn)
        
        bits_row.addStretch()
        output_layout.addLayout(bits_row)
        
        # Status Label (A-law 8kHz ist Standard für Sipgate)
        self._output_status = QLabel("Aktuell: A-law, 8kHz (SDP)")
        self._output_status.setStyleSheet("font-size: 9px; color: #666;")
        output_layout.addWidget(self._output_status)
        
        # Replay Button für Test-Modus
        self._replay_btn = QPushButton("🔄 Audio neu abspielen")
        self._replay_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; "
            "padding: 5px 10px; font-size: 10px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #138496; }"
        )
        self._replay_btn.clicked.connect(self._on_replay_clicked)
        output_layout.addWidget(self._replay_btn)
        
        active_layout.addWidget(output_frame)
        
        layout.addWidget(self._active_frame)
        self._active_frame.hide()

        # === Idle State mit Test-Button ===
        self._idle_frame = QFrame()
        idle_layout = QVBoxLayout(self._idle_frame)

        self._idle_label = QLabel("Warte auf Anruf...")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_label.setStyleSheet("color: gray; font-size: 14px;")
        idle_layout.addWidget(self._idle_label)

        # === AI Model Auswahl ===
        model_frame = QFrame()
        model_frame.setStyleSheet("background-color: #e9ecef; border-radius: 5px; padding: 5px;")
        model_layout = QHBoxLayout(model_frame)
        model_layout.setContentsMargins(10, 5, 10, 5)

        model_label = QLabel("AI Model:")
        model_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #333;")
        model_layout.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.addItem("gpt-realtime", "gpt-realtime")
        self._model_combo.addItem("gpt-4o-realtime-preview", "gpt-4o-realtime-preview-2024-12-17")
        self._model_combo.setStyleSheet(
            "QComboBox { padding: 5px; font-size: 11px; min-width: 180px; "
            "background-color: white; color: #333; border: 1px solid #ccc; border-radius: 3px; }"
            "QComboBox:drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: white; color: #333; selection-background-color: #007bff; }"
        )
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_combo)

        model_layout.addStretch()
        idle_layout.addWidget(model_frame)

        # Test-Anruf Button
        self._test_call_btn = QPushButton("🎤 Test-Anruf starten (Mikrofon)")
        self._test_call_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; "
            "padding: 15px 30px; font-size: 16px; border-radius: 8px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #0056b3; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self._test_call_btn.clicked.connect(self._on_test_call_clicked)
        idle_layout.addWidget(self._test_call_btn)

        test_info = QLabel("Testet die AI-Verbindung mit deinem Mikrofon")
        test_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_info.setStyleSheet("color: gray; font-size: 11px;")
        idle_layout.addWidget(test_info)

        layout.addWidget(self._idle_frame)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Verbindet die Signals."""
        self._signals.sip_registration_changed.connect(self._on_registration_changed)
        self._signals.call_state_changed.connect(self._on_call_state_changed)
        self._signals.incoming_call.connect(self._on_incoming_call)
        self._signals.ai_mute_changed.connect(self._on_ai_mute_changed)

    def _on_registration_changed(self, state: RegistrationState, error: str) -> None:
        """Handler für SIP Registrierungsänderung."""
        status_map = {
            RegistrationState.UNREGISTERED: ("Nicht verbunden", "gray"),
            RegistrationState.REGISTERING: ("Verbinde...", "orange"),
            RegistrationState.REGISTERED: ("Registriert", "green"),
            RegistrationState.FAILED: (f"Fehler: {error}", "red"),
        }
        text, color = status_map.get(state, ("Unbekannt", "gray"))
        self._sip_status.setText(text)
        self._sip_status.setStyleSheet(f"color: {color};")

    def _on_call_state_changed(self, state: CallState) -> None:
        """Handler für Call State Änderung."""
        self._current_call_state = state

        # Alle Frames verstecken
        self._call_frame.hide()
        self._active_frame.hide()
        self._idle_frame.hide()

        if state == CallState.IDLE:
            self._idle_label.setText("Warte auf Anruf...")
            self._idle_frame.show()
            self._test_call_btn.setEnabled(True)
        elif state == CallState.RINGING:
            self._call_frame.show()
        elif state == CallState.ACTIVE:
            self._active_frame.show()
            self._test_call_btn.setEnabled(False)
        elif state == CallState.ENDED:
            self._idle_label.setText("Anruf beendet")
            self._idle_frame.show()
            self._test_call_btn.setEnabled(True)

    def _on_incoming_call(self, caller_id: str) -> None:
        """Handler für eingehenden Anruf."""
        self._caller_id_label.setText(caller_id or "Unbekannt")

    def _on_ai_mute_changed(self, muted: bool) -> None:
        """Handler für AI Mute Status."""
        self._mute_btn.setChecked(muted)

    def _on_accept_clicked(self) -> None:
        """Handler für Accept Button."""
        self._signals.action_accept_call.emit()

    def _on_reject_clicked(self) -> None:
        """Handler für Reject Button."""
        self._signals.action_reject_call.emit()

    def _on_hangup_clicked(self) -> None:
        """Handler für Hangup Button."""
        self._signals.action_hangup.emit()

    def _on_mute_clicked(self) -> None:
        """Handler für Mute Button."""
        self._signals.action_mute_ai.emit(self._mute_btn.isChecked())

    def _codec_btn_style(self) -> str:
        """Style für Codec-Buttons."""
        return (
            "QPushButton { background-color: #6c757d; color: white; "
            "padding: 3px 8px; font-size: 10px; border-radius: 3px; min-width: 45px; }"
            "QPushButton:hover { background-color: #5a6268; }"
            "QPushButton:checked { background-color: #28a745; }"
        )

    def _on_codec_clicked(self, codec: str) -> None:
        """Handler für Codec-Button Click."""
        # Alle anderen unchecken, diesen checken
        self._codec_pcm8_btn.setChecked(codec == "pcm8")
        self._codec_ulaw_btn.setChecked(codec == "ulaw")
        self._codec_alaw_btn.setChecked(codec == "alaw")
        self._current_codec = codec
        self._update_output()
    
    def _on_rate_clicked(self, rate: int) -> None:
        """Handler für Rate-Button Click."""
        # Alle anderen unchecken, diesen checken
        self._rate_8k_btn.setChecked(rate == 8000)
        self._rate_16k_btn.setChecked(rate == 16000)
        self._rate_24k_btn.setChecked(rate == 24000)
        self._current_rate = rate
        self._update_output()
    
    def _on_bits_clicked(self, bits: int) -> None:
        """Handler für Bits-Button Click."""
        # Alle anderen unchecken, diesen checken
        self._bits_8_btn.setChecked(bits == 8)
        self._bits_16_btn.setChecked(bits == 16)
        self._current_bits = bits
        self._update_output()
    
    def _update_output(self) -> None:
        """Aktualisiert Output-Einstellungen und ruft Callback auf."""
        codec = getattr(self, '_current_codec', 'alaw')
        rate = getattr(self, '_current_rate', 8000)
        bits = getattr(self, '_current_bits', 8)
        
        # Status aktualisieren
        self._output_status.setText(f"Aktuell: {codec}, {rate//1000}kHz, {bits}-bit")
        
        # Callback aufrufen
        if hasattr(self, '_on_output_callback') and self._on_output_callback:
            self._on_output_callback(codec, rate, bits)

    def set_codec_callback(self, callback) -> None:
        """Setzt den Callback für Output-Änderungen. callback(codec, rate, bits)"""
        self._on_output_callback = callback
    
    def set_replay_callback(self, callback) -> None:
        """Setzt den Callback für Replay-Button. callback()"""
        self._on_replay_callback = callback
    
    def _on_replay_clicked(self) -> None:
        """Handler für Replay-Button."""
        if hasattr(self, '_on_replay_callback') and self._on_replay_callback:
            self._on_replay_callback()

    def _on_test_call_clicked(self) -> None:
        """Handler für Test-Anruf Button."""
        if self._on_start_local_test:
            self._on_start_local_test()

    def _on_model_changed(self, index: int) -> None:
        """Handler für Model-Auswahl Änderung."""
        model = self._model_combo.itemData(index)
        if model:
            self._signals.action_change_model.emit(model)

    def set_local_test_available(self, available: bool) -> None:
        """Aktiviert/Deaktiviert den Test-Anruf Button."""
        self._test_call_btn.setEnabled(available)
        if not available:
            self._test_call_btn.setText("🎤 Test-Anruf (nicht verfügbar)")

    def update_duration(self, seconds: float) -> None:
        """Aktualisiert die Anrufdauer-Anzeige."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        self._duration_label.setText(f"{minutes:02d}:{secs:02d}")

    def set_auto_accept_enabled(self, enabled: bool) -> None:
        """Zeigt/Versteckt den Auto-Accept Indikator."""
        if enabled:
            self._auto_accept_label.setText("Auto-Accept AN")
            self._auto_accept_label.show()
        else:
            self._auto_accept_label.hide()

    def set_current_model(self, model: str) -> None:
        """Setzt das aktuell ausgewählte Model in der ComboBox."""
        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == model:
                self._model_combo.setCurrentIndex(i)
                break

    def get_current_model(self) -> str:
        """Gibt das aktuell ausgewählte Model zurück."""
        return self._model_combo.currentData() or "gpt-realtime"
