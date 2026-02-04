"""
Audio Test Panel für Mikrofon/Lautsprecher Tests.

Ermöglicht:
- Auswahl von Mikrofon und Lautsprecher
- Aufnahme von Audio
- Wiedergabe der Aufnahme
- Persistente Speicherung der Geräteauswahl
"""

import json
import logging
import wave
from pathlib import Path
from typing import Optional
from datetime import datetime
import numpy as np

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
    QProgressBar,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sd = None
    SOUNDDEVICE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Einstellungen Datei
SETTINGS_FILE = Path(__file__).parent.parent / "audio_settings.json"


class AudioRecorder(QObject):
    """Nimmt Audio auf und spielt es ab."""
    
    # Signals
    recording_started = Signal()
    recording_stopped = Signal(float)  # Dauer in Sekunden
    playback_started = Signal()
    playback_stopped = Signal()
    level_changed = Signal(float)  # 0.0 - 1.0
    
    def __init__(self, sample_rate: int = 16000):
        super().__init__()
        self._sample_rate = sample_rate
        self._recording = False
        self._playing = False
        self._recorded_data: list[np.ndarray] = []
        self._playback_data: Optional[np.ndarray] = None
        self._playback_pos = 0
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.OutputStream] = None
        self._level_timer = QTimer()
        self._level_timer.timeout.connect(self._update_level)
        self._current_level = 0.0
        
    def start_recording(self, device_id: Optional[int] = None) -> bool:
        """Startet die Aufnahme."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.error("sounddevice nicht verfügbar")
            return False
            
        if self._recording:
            return False
            
        self._recorded_data = []
        self._recording = True
        
        try:
            self._input_stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype=np.int16,
                device=device_id,
                blocksize=1024,
                callback=self._record_callback,
            )
            self._input_stream.start()
            self._level_timer.start(50)
            self.recording_started.emit()
            logger.info(f"Aufnahme gestartet (Device: {device_id})")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Starten der Aufnahme: {e}")
            self._recording = False
            return False
    
    def stop_recording(self) -> Optional[bytes]:
        """Stoppt die Aufnahme und gibt die Daten zurück."""
        if not self._recording:
            return None
            
        self._recording = False
        self._level_timer.stop()
        
        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None
        
        if self._recorded_data:
            # Alle Chunks zusammenfügen
            self._playback_data = np.concatenate(self._recorded_data)
            duration = len(self._playback_data) / self._sample_rate
            self.recording_stopped.emit(duration)
            logger.info(f"Aufnahme gestoppt: {duration:.1f}s, {len(self._playback_data)} samples")
            return self._playback_data.tobytes()
        
        return None
    
    def start_playback(self, device_id: Optional[int] = None) -> bool:
        """Spielt die Aufnahme ab."""
        if not SOUNDDEVICE_AVAILABLE:
            return False
            
        if self._playing or self._playback_data is None:
            return False
            
        self._playing = True
        self._playback_pos = 0
        
        try:
            self._output_stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype=np.int16,
                device=device_id,
                blocksize=1024,
                callback=self._playback_callback,
            )
            self._output_stream.start()
            self.playback_started.emit()
            logger.info(f"Wiedergabe gestartet (Device: {device_id})")
            return True
        except Exception as e:
            logger.error(f"Fehler bei Wiedergabe: {e}")
            self._playing = False
            return False
    
    def stop_playback(self) -> None:
        """Stoppt die Wiedergabe."""
        if not self._playing:
            return
            
        self._playing = False
        
        if self._output_stream:
            self._output_stream.stop()
            self._output_stream.close()
            self._output_stream = None
        
        self.playback_stopped.emit()
        logger.info("Wiedergabe gestoppt")
    
    def _record_callback(self, indata, frames, time_info, status):
        """Callback für Aufnahme."""
        if status:
            logger.warning(f"Record status: {status}")
        if self._recording:
            self._recorded_data.append(indata.copy().flatten())
            # Level berechnen
            self._current_level = np.abs(indata).mean() / 32768.0
    
    def _playback_callback(self, outdata, frames, time_info, status):
        """Callback für Wiedergabe."""
        if status:
            logger.warning(f"Playback status: {status}")
            
        if not self._playing or self._playback_data is None:
            outdata.fill(0)
            return
            
        remaining = len(self._playback_data) - self._playback_pos
        
        if remaining <= 0:
            outdata.fill(0)
            self._playing = False
            # Timer für Signal (kann nicht direkt im Callback)
            QTimer.singleShot(0, self.playback_stopped.emit)
            return
            
        chunk_size = min(frames, remaining)
        outdata[:chunk_size, 0] = self._playback_data[self._playback_pos:self._playback_pos + chunk_size]
        outdata[chunk_size:, 0] = 0
        self._playback_pos += chunk_size
    
    def _update_level(self):
        """Aktualisiert den Level-Meter."""
        self.level_changed.emit(min(1.0, self._current_level * 3))
    
    @property
    def has_recording(self) -> bool:
        """Gibt zurück ob eine Aufnahme vorhanden ist."""
        return self._playback_data is not None and len(self._playback_data) > 0
    
    @property
    def recording_duration(self) -> float:
        """Gibt die Dauer der Aufnahme in Sekunden zurück."""
        if self._playback_data is None:
            return 0.0
        return len(self._playback_data) / self._sample_rate
    
    def get_recorded_data(self) -> Optional[bytes]:
        """Gibt die aufgenommenen Daten zurück."""
        if self._playback_data is None:
            return None
        return self._playback_data.tobytes()


class AudioTestPanel(QWidget):
    """
    Panel zum Testen von Audio-Geräten.
    
    Features:
    - Mikrofon-Auswahl
    - Lautsprecher-Auswahl
    - Record-Button
    - Play-Button
    - Level-Meter
    """
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._recorder = AudioRecorder()
        self._saved_input: Optional[int] = None
        self._saved_output: Optional[int] = None
        self._loading_settings = False  # Flag um doppeltes Speichern zu verhindern
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
        self._refresh_devices()
        self._apply_saved_settings()
    
    def _setup_ui(self) -> None:
        """Erstellt die UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Titel
        title = QLabel("🔊 Audio-Test")
        title.setFont(QFont("", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Geräte-Auswahl Frame
        devices_frame = QFrame()
        devices_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        devices_layout = QVBoxLayout(devices_frame)
        
        # Mikrofon-Auswahl
        mic_layout = QHBoxLayout()
        mic_label = QLabel("Mikrofon:")
        mic_label.setMinimumWidth(80)
        mic_layout.addWidget(mic_label)
        
        self._mic_combo = QComboBox()
        self._mic_combo.setMinimumWidth(200)
        self._mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_layout.addWidget(self._mic_combo, stretch=1)
        
        devices_layout.addLayout(mic_layout)
        
        # Lautsprecher-Auswahl
        speaker_layout = QHBoxLayout()
        speaker_label = QLabel("Lautsprecher:")
        speaker_label.setMinimumWidth(80)
        speaker_layout.addWidget(speaker_label)
        
        self._speaker_combo = QComboBox()
        self._speaker_combo.setMinimumWidth(200)
        self._speaker_combo.currentIndexChanged.connect(self._on_speaker_changed)
        speaker_layout.addWidget(self._speaker_combo, stretch=1)
        
        devices_layout.addLayout(speaker_layout)
        
        # Refresh Button
        self._refresh_btn = QPushButton("🔄 Geräte aktualisieren")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        devices_layout.addWidget(self._refresh_btn)
        
        layout.addWidget(devices_frame)
        
        # Record/Play Frame
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self._record_btn = QPushButton("🔴 Aufnehmen")
        self._record_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #c82333; }"
            "QPushButton:checked { background-color: #28a745; }"
        )
        self._record_btn.setCheckable(True)
        self._record_btn.clicked.connect(self._on_record_clicked)
        btn_layout.addWidget(self._record_btn)
        
        self._play_btn = QPushButton("▶️ Abspielen")
        self._play_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0056b3; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play_clicked)
        btn_layout.addWidget(self._play_btn)
        
        self._save_btn = QPushButton("💾 Speichern")
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; "
            "padding: 10px 20px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #218838; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self._save_btn)
        
        controls_layout.addLayout(btn_layout)
        
        # Level Meter
        level_layout = QHBoxLayout()
        level_label = QLabel("Pegel:")
        level_layout.addWidget(level_label)
        
        self._level_bar = QProgressBar()
        self._level_bar.setRange(0, 100)
        self._level_bar.setValue(0)
        self._level_bar.setTextVisible(False)
        self._level_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #ccc; border-radius: 3px; height: 15px; }"
            "QProgressBar::chunk { background-color: #28a745; }"
        )
        level_layout.addWidget(self._level_bar, stretch=1)
        
        controls_layout.addLayout(level_layout)
        
        # Status
        self._status_label = QLabel("Bereit")
        self._status_label.setStyleSheet("color: gray;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self._status_label)
        
        layout.addWidget(controls_frame)
    
    def _connect_signals(self) -> None:
        """Verbindet Signals."""
        self._recorder.recording_started.connect(self._on_recording_started)
        self._recorder.recording_stopped.connect(self._on_recording_stopped)
        self._recorder.playback_started.connect(self._on_playback_started)
        self._recorder.playback_stopped.connect(self._on_playback_stopped)
        self._recorder.level_changed.connect(self._on_level_changed)
    
    def _refresh_devices(self) -> None:
        """Aktualisiert die Gerätelisten."""
        if not SOUNDDEVICE_AVAILABLE:
            self._status_label.setText("sounddevice nicht verfügbar!")
            return
        
        self._loading_settings = True
        try:
            # Aktuelle Auswahl merken
            current_mic = self._mic_combo.currentData()
            current_speaker = self._speaker_combo.currentData()
            
            # Listen leeren
            self._mic_combo.clear()
            self._speaker_combo.clear()
            
            # Geräte auflisten
            devices = sd.query_devices()
            default_input, default_output = sd.default.device
            
            for i, dev in enumerate(devices):
                name = dev["name"]
                
                # Input-Geräte
                if dev["max_input_channels"] > 0:
                    display_name = f"{name}"
                    if i == default_input:
                        display_name += " (Standard)"
                    self._mic_combo.addItem(display_name, i)
                
                # Output-Geräte
                if dev["max_output_channels"] > 0:
                    display_name = f"{name}"
                    if i == default_output:
                        display_name += " (Standard)"
                    self._speaker_combo.addItem(display_name, i)
            
            # Vorherige Auswahl wiederherstellen
            if current_mic is not None:
                idx = self._mic_combo.findData(current_mic)
                if idx >= 0:
                    self._mic_combo.setCurrentIndex(idx)
            
            if current_speaker is not None:
                idx = self._speaker_combo.findData(current_speaker)
                if idx >= 0:
                    self._speaker_combo.setCurrentIndex(idx)
            
            self._status_label.setText(f"{self._mic_combo.count()} Mikrofone, {self._speaker_combo.count()} Lautsprecher")
        finally:
            self._loading_settings = False
    
    def _on_mic_changed(self, index: int) -> None:
        """Handler für Mikrofon-Änderung."""
        if not self._loading_settings:
            self._save_settings()
            logger.info(f"Mikrofon geändert: {self._mic_combo.currentText()}")
    
    def _on_speaker_changed(self, index: int) -> None:
        """Handler für Lautsprecher-Änderung."""
        if not self._loading_settings:
            self._save_settings()
            logger.info(f"Lautsprecher geändert: {self._speaker_combo.currentText()}")
    
    def _on_record_clicked(self) -> None:
        """Handler für Record-Button."""
        if self._record_btn.isChecked():
            # Start Recording
            mic_id = self._mic_combo.currentData()
            if self._recorder.start_recording(mic_id):
                self._record_btn.setText("⏹️ Stopp")
                self._play_btn.setEnabled(False)
            else:
                self._record_btn.setChecked(False)
                self._status_label.setText("Fehler beim Starten!")
        else:
            # Stop Recording
            self._recorder.stop_recording()
    
    def _on_play_clicked(self) -> None:
        """Handler für Play-Button."""
        if self._recorder._playing:
            self._recorder.stop_playback()
        else:
            speaker_id = self._speaker_combo.currentData()
            self._recorder.start_playback(speaker_id)
    
    def _on_recording_started(self) -> None:
        """Handler für Aufnahme gestartet."""
        self._status_label.setText("🔴 Aufnahme läuft... Sprich jetzt!")
        self._status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _on_recording_stopped(self, duration: float) -> None:
        """Handler für Aufnahme gestoppt."""
        self._record_btn.setChecked(False)
        self._record_btn.setText("🔴 Aufnehmen")
        self._play_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._status_label.setText(f"✅ Aufnahme: {duration:.1f} Sekunden")
        self._status_label.setStyleSheet("color: green;")
        self._level_bar.setValue(0)
        
        # Automatisch speichern
        saved_path = self.save_recording()
        if saved_path:
            self._last_saved_path = saved_path
    
    def _on_playback_started(self) -> None:
        """Handler für Wiedergabe gestartet."""
        self._play_btn.setText("⏹️ Stopp")
        self._status_label.setText("▶️ Wiedergabe...")
        self._status_label.setStyleSheet("color: blue;")
    
    def _on_playback_stopped(self) -> None:
        """Handler für Wiedergabe gestoppt."""
        self._play_btn.setText("▶️ Abspielen")
        self._status_label.setText("✅ Wiedergabe beendet")
        self._status_label.setStyleSheet("color: green;")
    
    def _on_level_changed(self, level: float) -> None:
        """Handler für Level-Änderung."""
        self._level_bar.setValue(int(level * 100))
    
    def _on_save_clicked(self) -> None:
        """Handler für Save-Button."""
        self.save_recording()
    
    def _save_settings(self) -> None:
        """Speichert die Geräteauswahl."""
        settings = {
            "input_device": self._mic_combo.currentData(),
            "output_device": self._speaker_combo.currentData(),
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f)
            logger.debug(f"Audio-Einstellungen gespeichert: {settings}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")
    
    def _load_settings(self) -> None:
        """Lädt die Geräteauswahl."""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                
                # Später anwenden (nach refresh_devices)
                self._saved_input = settings.get("input_device")
                self._saved_output = settings.get("output_device")
                logger.info(f"Audio-Einstellungen geladen: Input={self._saved_input}, Output={self._saved_output}")
        except Exception as e:
            logger.error(f"Fehler beim Laden: {e}")
            self._saved_input = None
            self._saved_output = None
    
    def _apply_saved_settings(self) -> None:
        """Wendet die gespeicherten Einstellungen auf die Combo-Boxen an."""
        self._loading_settings = True
        try:
            if self._saved_input is not None:
                idx = self._mic_combo.findData(self._saved_input)
                if idx >= 0:
                    self._mic_combo.setCurrentIndex(idx)
                    logger.info(f"Mikrofon wiederhergestellt: {self._mic_combo.currentText()}")
            
            if self._saved_output is not None:
                idx = self._speaker_combo.findData(self._saved_output)
                if idx >= 0:
                    self._speaker_combo.setCurrentIndex(idx)
                    logger.info(f"Lautsprecher wiederhergestellt: {self._speaker_combo.currentText()}")
        finally:
            self._loading_settings = False
    
    def get_selected_devices(self) -> tuple[Optional[int], Optional[int]]:
        """Gibt die ausgewählten Geräte-IDs zurück."""
        return (
            self._mic_combo.currentData(),
            self._speaker_combo.currentData(),
        )
    
    def get_recorded_audio(self) -> Optional[bytes]:
        """Gibt die aufgenommenen Audio-Daten zurück."""
        return self._recorder.get_recorded_data()
    
    def save_recording(self, filepath: Optional[Path] = None) -> Optional[Path]:
        """
        Speichert die Aufnahme als WAV-Datei.
        
        Args:
            filepath: Optionaler Pfad. Wenn None, wird automatisch generiert.
            
        Returns:
            Pfad zur gespeicherten Datei oder None bei Fehler.
        """
        data = self._recorder.get_recorded_data()
        if data is None:
            logger.error("Keine Aufnahme zum Speichern")
            return None
        
        # Automatischen Dateinamen generieren
        if filepath is None:
            recordings_dir = Path(__file__).parent.parent / "recordings"
            recordings_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = recordings_dir / f"recording_{timestamp}.wav"
        
        try:
            # Als WAV speichern
            with wave.open(str(filepath), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self._recorder._sample_rate)
                wav_file.writeframes(data)
            
            logger.info(f"Aufnahme gespeichert: {filepath}")
            self._status_label.setText(f"💾 Gespeichert: {filepath.name}")
            return filepath
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")
            self._status_label.setText(f"Fehler: {e}")
            return None


# Demo/Test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    panel = AudioTestPanel()
    panel.setWindowTitle("Audio Test")
    panel.resize(400, 300)
    panel.show()
    
    sys.exit(app.exec())
