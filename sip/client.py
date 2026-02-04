"""
SIP Client für Sipgate Integration.

Verwendet pyVoIP (pure Python) für SIP/RTP Handling.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Any
from dataclasses import dataclass
import numpy as np

from config import SIPConfig, AudioConfig
from core.state import CallState, RegistrationState
from core.signals import AppSignals

logger = logging.getLogger(__name__)


# pyVoIP importieren
try:
    from pyVoIP.VoIP import VoIPPhone, InvalidStateError, CallState as PyVoIPCallState
    from pyVoIP.VoIP import VoIPCall

    PYVOIP_AVAILABLE = True
    logger.info("pyVoIP verfügbar")
except ImportError:
    PYVOIP_AVAILABLE = False
    logger.error("pyVoIP nicht verfügbar - SIP-Funktionalität deaktiviert!")
    logger.error("Bitte installieren: pip install pyVoIP")


@dataclass
class CallInfo:
    """Interne Call-Informationen."""

    call_id: str
    remote_uri: str
    remote_name: str = ""
    state: CallState = CallState.IDLE


class SIPClient:
    """
    SIP Client für Anrufverwaltung.

    Verwendet pyVoIP für SIP/RTP Handling.
    Unterstützt automatische Reconnection bei Verbindungsverlust.
    """

    # Reconnect-Konfiguration
    RECONNECT_DELAY_INITIAL = 1.0  # Sekunden
    RECONNECT_DELAY_MAX = 30.0  # Sekunden
    RECONNECT_DELAY_MULTIPLIER = 2.0

    def __init__(
        self,
        sip_config: SIPConfig,
        audio_config: AudioConfig,
        signals: AppSignals,
    ):
        """
        Initialisiert den SIP Client.

        Args:
            sip_config: SIP Verbindungseinstellungen
            audio_config: Audio-Einstellungen
            signals: Qt Signals für UI-Updates

        Raises:
            RuntimeError: Wenn pyVoIP nicht installiert ist
        """
        self._sip_config = sip_config
        self._audio_config = audio_config
        self._signals = signals

        self._registration_state = RegistrationState.UNREGISTERED
        self._current_call: Optional[CallInfo] = None
        self._current_voip_call: Optional[Any] = None  # pyVoIP VoIPCall
        self._running = False
        self._lock = threading.Lock()

        # Callbacks für Audio
        self._on_audio_frame: Optional[Callable[[bytes], None]] = None

        # Auto-Accept: Direkt im pyVoIP Callback annehmen
        self._auto_accept_enabled = False
        
        # Callback wenn Anruf angenommen wurde (für Controller)
        self._on_call_accepted: Optional[Callable[[], None]] = None

        # Reconnect State
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_delay = self.RECONNECT_DELAY_INITIAL
        self._should_reconnect = True

        # pyVoIP Phone
        self._phone: Optional[VoIPPhone] = None
        
        # Audio Thread
        self._audio_thread: Optional[threading.Thread] = None
        self._audio_running = False

        if not PYVOIP_AVAILABLE:
            raise RuntimeError(
                "pyVoIP ist nicht installiert! "
                "Bitte installieren: pip install pyVoIP"
            )

    def register(self) -> None:
        """Startet die SIP Registrierung."""
        self._running = True
        self._should_reconnect = True
        self._set_registration_state(RegistrationState.REGISTERING)

        try:
            # pyVoIP Phone erstellen
            self._phone = VoIPPhone(
                server=self._sip_config.server,
                port=self._sip_config.port,
                username=self._sip_config.username,
                password=self._sip_config.password,
                callCallback=self._on_incoming_call_pyvoip,
                sipPort=5060,  # Lokaler SIP Port
                rtpPortLow=10000,
                rtpPortHigh=20000,
            )

            # Phone starten
            self._phone.start()

            self._set_registration_state(RegistrationState.REGISTERED)
            logger.info(f"SIP registriert bei {self._sip_config.server}")

        except Exception as e:
            logger.error(f"SIP Registrierung fehlgeschlagen: {e}")
            self._set_registration_state(RegistrationState.FAILED, str(e))
            self._schedule_reconnect()

    def unregister(self) -> None:
        """Beendet die SIP Registrierung."""
        self._running = False
        self._should_reconnect = False

        if self._phone:
            try:
                self._phone.stop()
            except Exception as e:
                logger.error(f"Fehler beim Abmelden: {e}")

        self._set_registration_state(RegistrationState.UNREGISTERED)

    def _schedule_reconnect(self) -> None:
        """Plant einen Reconnect-Versuch."""
        if not self._should_reconnect or not self._running:
            return

        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return

        def reconnect_task():
            logger.info(f"Reconnect in {self._reconnect_delay:.1f}s...")
            time.sleep(self._reconnect_delay)

            if self._should_reconnect and self._running:
                logger.info("Versuche Reconnect...")
                self.register()

                # Exponential backoff
                self._reconnect_delay = min(
                    self._reconnect_delay * self.RECONNECT_DELAY_MULTIPLIER,
                    self.RECONNECT_DELAY_MAX,
                )

        self._reconnect_thread = threading.Thread(
            target=reconnect_task,
            name="SIP-Reconnect",
            daemon=True,
        )
        self._reconnect_thread.start()

    def _reset_reconnect_delay(self) -> None:
        """Setzt den Reconnect-Delay zurück nach erfolgreicher Verbindung."""
        self._reconnect_delay = self.RECONNECT_DELAY_INITIAL

    def _on_incoming_call_pyvoip(self, call: Any) -> None:
        """
        pyVoIP Callback für eingehenden Anruf.
        
        Wird in einem separaten Thread von pyVoIP aufgerufen.
        WICHTIG: Bei pyVoIP muss der Anruf im Callback behandelt werden!
        """
        try:
            # Call-Info extrahieren
            caller_id = "Unbekannt"
            
            try:
                request = call.request
                # From-Header parsen
                if hasattr(request, 'headers') and 'From' in request.headers:
                    from_header = str(request.headers['From'])
                    # sip:number@domain -> number
                    if "sip:" in from_header:
                        caller_id = from_header.split("sip:")[1].split("@")[0]
                        # Anführungszeichen und < > entfernen
                        caller_id = caller_id.replace('"', '').replace('<', '').replace('>', '').strip()
            except Exception as e:
                logger.warning(f"Caller-ID Extraktion fehlgeschlagen: {e}")

            logger.info(f"Eingehender Anruf von: {caller_id}")

            with self._lock:
                self._current_voip_call = call
                self._current_call = CallInfo(
                    call_id=str(id(call)),
                    remote_uri=caller_id,
                    remote_name=caller_id,
                    state=CallState.RINGING,
                )

            # UI benachrichtigen (thread-safe über Qt Signal)
            self._signals.incoming_call.emit(caller_id)
            self._emit_call_state_changed(CallState.RINGING)

            # Auto-Accept: Direkt hier annehmen!
            if self._auto_accept_enabled:
                logger.info("Auto-Accept: Nehme Anruf automatisch an...")
                time.sleep(0.3)  # Kurze Verzögerung für Stabilität
                
                try:
                    call.answer()
                    logger.info("Anruf angenommen!")
                    
                    with self._lock:
                        if self._current_call:
                            self._current_call.state = CallState.ACTIVE
                    
                    self._emit_call_state_changed(CallState.ACTIVE)
                    
                    # Controller benachrichtigen dass Anruf angenommen wurde
                    if self._on_call_accepted:
                        self._on_call_accepted()
                    
                    # Audio verarbeiten
                    self._process_audio(call)
                    
                except Exception as e:
                    logger.error(f"Auto-Accept fehlgeschlagen: {e}")
                    self._end_call("auto_accept_failed")
                    return
            else:
                # Manueller Modus: Warte auf Annahme
                logger.info("Warte auf manuelle Annahme...")
                while self._running:
                    if not self._current_voip_call:
                        break
                        
                    try:
                        call_state = call.state
                    except:
                        break
                        
                    if call_state == PyVoIPCallState.ENDED:
                        break
                    elif call_state == PyVoIPCallState.ANSWERED:
                        # Anruf wurde manuell angenommen
                        self._process_audio(call)
                        break
                        
                    time.sleep(0.1)

            # Cleanup
            self._end_call("call_ended")
            
        except InvalidStateError as e:
            logger.warning(f"Anruf in ungültigem Zustand: {e}")
            self._end_call("invalid_state")
        except Exception as e:
            logger.error(f"Fehler bei eingehendem Anruf: {e}", exc_info=True)
            self._end_call("error")

    def _process_audio(self, call: Any) -> None:
        """
        Verarbeitet Audio während eines aktiven Anrufs.
        
        Liest Audio vom Anrufer und sendet AI-Audio zurück.
        """
        logger.info("Audio-Verarbeitung gestartet")
        self._audio_running = True
        
        frames_read = 0
        frames_sent = 0
        last_log_time = time.time()
        
        # Debug: Audio in Datei speichern
        debug_audio_file = None
        try:
            debug_audio_file = open("recordings/sip_audio_raw.pcm", "wb")
            logger.info("Debug: Speichere SIP Audio in recordings/sip_audio_raw.pcm")
        except Exception as e:
            logger.warning(f"Konnte Debug-Audio nicht speichern: {e}")
        
        try:
            while self._audio_running and self._running:
                try:
                    call_state = call.state
                except:
                    logger.warning("Konnte Call-State nicht lesen, beende Audio")
                    break
                    
                if call_state != PyVoIPCallState.ANSWERED:
                    logger.info(f"Call nicht mehr ANSWERED (state={call_state}), beende Audio")
                    break

                # Audio vom Anrufer lesen
                try:
                    # pyVoIP read_audio: length in bytes, returns bytes or None
                    audio_data = call.read_audio(length=160, blocking=False)  # 20ms @ 8kHz
                    
                    if audio_data and len(audio_data) > 0:
                        frames_read += 1
                        
                        # Debug: Raw Audio speichern
                        if debug_audio_file:
                            debug_audio_file.write(audio_data)
                        
                        if self._on_audio_frame:
                            # pyVoIP liefert 8kHz 8-bit ulaw - konvertiere zu 16kHz 16-bit PCM
                            converted = self._convert_8k_to_16k(audio_data)
                            self._on_audio_frame(converted)
                        
                        # Log alle 2 Sekunden
                        now = time.time()
                        if now - last_log_time >= 2.0:
                            logger.info(f"Audio: {frames_read} Frames gelesen, {len(audio_data)} bytes/frame")
                            last_log_time = now
                            
                except Exception as e:
                    error_str = str(e).lower()
                    if "not answered" not in error_str and "call not" not in error_str:
                        logger.debug(f"Audio lesen Fehler: {e}")

                # Audio an Anrufer senden (von AI)
                # TODO: Output Buffer lesen und an call.write_audio() senden
                
                time.sleep(0.01)  # 10ms Sleep
                
        except Exception as e:
            logger.error(f"Audio-Verarbeitung Fehler: {e}", exc_info=True)
        finally:
            self._audio_running = False
            if debug_audio_file:
                debug_audio_file.close()
                logger.info("Debug Audio-Datei gespeichert")
            logger.info(f"Audio-Verarbeitung beendet - {frames_read} Frames gelesen")

    def _convert_8k_to_16k(self, data: bytes) -> bytes:
        """
        Konvertiert 8kHz G.711 u-law Audio zu 16kHz 16-bit PCM.
        
        pyVoIP liefert G.711 u-law encoded Audio.
        Wir müssen erst dekodieren, dann upsamplen.
        """
        # G.711 u-law Dekodierungstabelle
        ulaw_table = self._get_ulaw_decode_table()
        
        # u-law zu 16-bit signed konvertieren
        samples_16bit = [ulaw_table[b] for b in data]
        
        # Numpy array für besseres Upsampling
        samples = np.array(samples_16bit, dtype=np.int16)
        
        # Upsample 8kHz -> 16kHz mit linearer Interpolation
        new_length = len(samples) * 2
        indices = np.linspace(0, len(samples) - 1, new_length)
        upsampled = np.interp(indices, np.arange(len(samples)), samples)
        
        return upsampled.astype(np.int16).tobytes()
    
    @staticmethod
    def _get_ulaw_decode_table() -> list:
        """Generiert u-law Dekodierungstabelle."""
        table = []
        for i in range(256):
            # Invertiere alle Bits
            byte = ~i & 0xFF
            
            # Extrahiere Komponenten
            sign = (byte & 0x80) >> 7
            exponent = (byte & 0x70) >> 4
            mantissa = byte & 0x0F
            
            # Berechne Sample
            sample = ((mantissa << 3) + 0x84) << exponent
            sample -= 0x84
            
            if sign:
                sample = -sample
            
            table.append(sample)
        
        return table

    def _convert_16k_to_8k(self, data: bytes) -> bytes:
        """
        Konvertiert 16kHz 16-bit Audio zu 8kHz 8-bit.
        
        Einfaches Downsampling.
        """
        import struct
        
        if len(data) == 0:
            return b''
            
        # 16-bit signed samples lesen
        num_samples = len(data) // 2
        samples = struct.unpack(f'<{num_samples}h', data)
        
        # Downsample 16kHz -> 8kHz (jeden zweiten Sample)
        downsampled = samples[::2]
        
        # 16-bit signed -> 8-bit unsigned
        samples_8bit = bytes([max(0, min(255, (s // 256) + 128)) for s in downsampled])
        
        return samples_8bit

    def accept_call(self) -> bool:
        """
        Nimmt den aktuellen eingehenden Anruf an.

        Returns:
            True wenn erfolgreich
        """
        with self._lock:
            if not self._current_call or self._current_call.state != CallState.RINGING:
                logger.warning("Kein eingehender Anruf zum Annehmen")
                return False

            if not self._current_voip_call:
                logger.error("Kein pyVoIP Call Objekt")
                return False

            try:
                self._current_voip_call.answer()
                self._current_call.state = CallState.ACTIVE
                self._emit_call_state_changed(CallState.ACTIVE)
                logger.info("Anruf angenommen")
                return True
            except Exception as e:
                logger.error(f"Fehler beim Annehmen: {e}")
                return False

    def reject_call(self) -> bool:
        """
        Lehnt den aktuellen eingehenden Anruf ab.

        Returns:
            True wenn erfolgreich
        """
        with self._lock:
            if not self._current_call or self._current_call.state != CallState.RINGING:
                return False

            if not self._current_voip_call:
                return False

            try:
                self._current_voip_call.deny()
                self._end_call("rejected")
                logger.info("Anruf abgelehnt")
                return True
            except Exception as e:
                logger.error(f"Fehler beim Ablehnen: {e}")
                return False

    def hangup(self) -> bool:
        """
        Legt den aktuellen Anruf auf.

        Returns:
            True wenn erfolgreich
        """
        with self._lock:
            if not self._current_call:
                return False

            self._audio_running = False

            if not self._current_voip_call:
                self._end_call("no_call_object")
                return True

            try:
                self._current_voip_call.hangup()
                self._end_call("user_hangup")
                logger.info("Aufgelegt")
                return True
            except Exception as e:
                logger.error(f"Fehler beim Auflegen: {e}")
                self._end_call("hangup_error")
                return False

    def send_audio(self, pcm_data: bytes) -> None:
        """
        Sendet Audio-Daten zum Remote-Teilnehmer.

        Args:
            pcm_data: PCM Audio-Daten (16kHz, mono, 16-bit)
        """
        if not self._current_call or self._current_call.state != CallState.ACTIVE:
            return

        if not self._current_voip_call:
            return

        try:
            # 16kHz 16-bit -> 8kHz 8-bit für pyVoIP
            converted = self._convert_16k_to_8k(pcm_data)
            self._current_voip_call.write_audio(converted)
        except Exception as e:
            logger.debug(f"Audio senden: {e}")

    def set_audio_callback(self, callback: Callable[[bytes], None]) -> None:
        """
        Setzt Callback für eingehende Audio-Frames.

        Args:
            callback: Funktion die mit PCM-Daten aufgerufen wird
        """
        self._on_audio_frame = callback

    def set_auto_accept(self, enabled: bool) -> None:
        """
        Aktiviert/Deaktiviert Auto-Accept.
        
        Wenn aktiviert, werden eingehende Anrufe automatisch angenommen.

        Args:
            enabled: True um Auto-Accept zu aktivieren
        """
        self._auto_accept_enabled = enabled
        logger.info(f"Auto-Accept: {'aktiviert' if enabled else 'deaktiviert'}")

    def set_call_accepted_callback(self, callback: Callable[[], None]) -> None:
        """
        Setzt Callback für angenommene Anrufe.
        
        Wird aufgerufen wenn ein Anruf angenommen wurde (manuell oder auto).
        Der Controller kann dann die Audio-Verarbeitung starten.

        Args:
            callback: Funktion ohne Parameter
        """
        self._on_call_accepted = callback

    # Für Rückwärtskompatibilität
    def set_auto_accept_callback(self, callback: Callable[[], None]) -> None:
        """Veraltet - verwende set_auto_accept() stattdessen."""
        pass

    def _set_registration_state(
        self, state: RegistrationState, error: str = ""
    ) -> None:
        """Setzt und emittiert Registrierungsstatus."""
        self._registration_state = state
        self._signals.sip_registration_changed.emit(state, error)

        # Reconnect bei Fehler oder Disconnect
        if state == RegistrationState.FAILED:
            self._schedule_reconnect()
        elif state == RegistrationState.REGISTERED:
            self._reset_reconnect_delay()

    def _emit_call_state_changed(self, state: CallState) -> None:
        """Emittiert Call State Change Signal."""
        self._signals.call_state_changed.emit(state)

    def _end_call(self, reason: str) -> None:
        """Beendet den aktuellen Anruf."""
        self._audio_running = False
        if self._current_call:
            self._current_call.state = CallState.ENDED
        self._emit_call_state_changed(CallState.ENDED)
        self._current_call = None
        self._current_voip_call = None

    def shutdown(self) -> None:
        """Fährt den SIP Client herunter."""
        self._running = False
        self._should_reconnect = False
        self._audio_running = False

        if self._current_call:
            self.hangup()

        self.unregister()

        logger.info("SIP Client heruntergefahren")


# Für Kompatibilität mit bestehendem Code
PJSUA2_AVAILABLE = PYVOIP_AVAILABLE


# Demo/Test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from core.signals import init_signals

    app = QApplication(sys.argv)
    signals = init_signals()

    from config import load_config

    try:
        config = load_config()
    except ValueError as e:
        print(f"Konfigurationsfehler: {e}")
        sys.exit(1)

    client = SIPClient(config.sip, config.audio, signals)

    def on_incoming(caller_id: str):
        print(f"Eingehender Anruf von: {caller_id}")

    def on_state(state: CallState):
        print(f"Call State: {state.value}")

    signals.incoming_call.connect(on_incoming)
    signals.call_state_changed.connect(on_state)

    print("Starte SIP Client...")
    client.register()

    print("Warte auf Anrufe... (Ctrl+C zum Beenden)")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nBeende...")
        client.shutdown()
