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
from scipy import signal as scipy_signal
import audioop

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
        
        # Test-Modus: Audio-Datei abspielen statt AI
        self._test_mode = False
        self._test_audio_file: Optional[str] = None
        self._test_audio_data: Optional[bytes] = None

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
            # Ermittle lokale IP für RTP
            local_ip = self._get_local_ip()
            logger.info(f"Verwende lokale IP für RTP: {local_ip}")
            
            # pyVoIP Phone erstellen
            self._phone = VoIPPhone(
                server=self._sip_config.server,
                port=self._sip_config.port,
                username=self._sip_config.username,
                password=self._sip_config.password,
                callCallback=self._on_incoming_call_pyvoip,
                myIP=local_ip,  # Explizit setzen für NAT
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
                    
                    # Automatische Codec-Erkennung aus SDP
                    self._detect_and_set_codec(call)
                    
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
                    # pyVoIP read_audio: liefert 8-bit unsigned PCM @ 8kHz
                    # 20ms @ 8kHz = 160 samples = 160 bytes (8-bit)
                    # blocking=False returns b"\x80"*length when no data available
                    audio_data = call.read_audio(length=160, blocking=False)  # 20ms @ 8kHz, 8-bit
                    
                    if audio_data and len(audio_data) > 0:
                        # Prüfe ob es echte Daten sind oder nur Stille-Placeholder
                        # pyVoIP gibt b"\x80"*length zurück wenn keine Daten verfügbar
                        # Bei 16-bit wäre das 0x8080 = -32640 für jedes Sample
                        is_silence_placeholder = all(b == 0x80 for b in audio_data)
                        
                        if not is_silence_placeholder:
                            frames_read += 1
                            
                            # Debug: Raw Audio speichern
                            if debug_audio_file:
                                debug_audio_file.write(audio_data)
                            
                            if self._on_audio_frame:
                                # WICHTIG: pyVoIP read_audio liefert BEREITS dekodiertes 
                                # lineares 8kHz 16-bit PCM (nicht u-law!)
                                # Wir müssen nur upsamplen von 8kHz zu 16kHz
                                converted = self._upsample_8k_to_16k(audio_data)
                                self._on_audio_frame(converted)
                        
                        # Log alle 2 Sekunden
                        now = time.time()
                        if now - last_log_time >= 2.0:
                            if is_silence_placeholder:
                                logger.warning(f"Audio: Keine RTP-Daten empfangen! (nur 0x80 placeholder)")
                            else:
                                logger.info(f"Audio: {frames_read} echte Frames gelesen")
                            last_log_time = now
                            
                except Exception as e:
                    error_str = str(e).lower()
                    # Prüfe auf Fehler die einen beendeten Call anzeigen
                    if "invalidstateerror" in error_str or "not answered" in error_str or "ended" in error_str:
                        logger.info("Call wurde beendet (erkannt bei read_audio)")
                        break
                    logger.debug(f"Audio lesen Fehler: {e}")

                # Audio an Anrufer senden
                try:
                    if self._test_mode and self._test_audio_data:
                        # TEST-MODUS: Audio-Datei abspielen
                        # Initialisiere oder re-initialisiere wenn nötig
                        if not hasattr(self, '_test_audio_converted') or self._test_audio_converted is None:
                            self._test_audio_converted = self._prepare_test_audio()
                            self._test_audio_pos = 0
                            logger.info(f"Test-Audio vorbereitet: {len(self._test_audio_converted)} bytes")
                        
                        if not hasattr(self, '_test_audio_pos'):
                            self._test_audio_pos = 0
                        
                        # 160 bytes pro Frame (20ms @ 8kHz, 8-bit)
                        chunk_size = 160
                        pos = self._test_audio_pos
                        
                        if self._test_audio_converted and pos < len(self._test_audio_converted):
                            chunk = self._test_audio_converted[pos:pos + chunk_size]
                            if len(chunk) < chunk_size:
                                chunk = chunk + b'\x80' * (chunk_size - len(chunk))
                            call.write_audio(chunk)
                            self._test_audio_pos += chunk_size
                            frames_sent += 1
                            
                            if frames_sent % 50 == 0:  # Log alle 1 Sekunde
                                logger.info(f"Test-Audio: {pos}/{len(self._test_audio_converted)} bytes gesendet")
                        else:
                            # Audio fertig, Stille senden
                            call.write_audio(b'\x80' * 160)
                    else:
                        # Normal: Stille für NAT keepalive
                        silence = b'\x80' * 160
                        call.write_audio(silence)
                    frames_sent += 1
                except Exception as e:
                    error_str = str(e).lower()
                    if "invalidstateerror" in error_str or "not answered" in error_str or "ended" in error_str:
                        logger.info("Call wurde beendet (erkannt bei write_audio)")
                        break
                    logger.debug(f"Audio senden Fehler: {e}")
                
                time.sleep(0.015)  # 15ms Sleep (ca. 20ms Frame Rate)
                
        except Exception as e:
            logger.error(f"Audio-Verarbeitung Fehler: {e}", exc_info=True)
        finally:
            self._audio_running = False
            if debug_audio_file:
                debug_audio_file.close()
                logger.info("Debug Audio-Datei gespeichert")
            logger.info(f"Audio-Verarbeitung beendet - {frames_read} Frames gelesen")
            
            # Wichtig: Anruf beenden wenn Audio-Loop endet
            self._end_call("call_ended")

    def _upsample_8k_to_16k(self, data: bytes) -> bytes:
        """
        Konvertiert 8kHz 8-bit unsigned PCM zu 16kHz 16-bit signed PCM.
        
        pyVoIP read_audio liefert 8-bit unsigned PCM:
        - Wertebereich: 0-255
        - Stille: 128
        - Wir müssen zu 16-bit signed konvertieren und upsamplen.
        """
        # Interpretiere als 8-bit unsigned
        samples_8bit = np.frombuffer(data, dtype=np.uint8)
        
        # Konvertiere 8-bit unsigned (0-255, center 128) zu 16-bit signed (-32768 to 32767)
        samples_16bit = (samples_8bit.astype(np.int16) - 128) * 256
        
        # Upsample 8kHz -> 16kHz mit linearer Interpolation
        new_length = len(samples_16bit) * 2
        indices = np.linspace(0, len(samples_16bit) - 1, new_length)
        upsampled = np.interp(indices, np.arange(len(samples_16bit)), samples_16bit)
        
        return upsampled.astype(np.int16).tobytes()
    
    def _convert_8k_to_16k(self, data: bytes) -> bytes:
        """
        VERALTET - pyVoIP liefert bereits lineares PCM!
        Verwende _upsample_8k_to_16k stattdessen.
        """
        return self._upsample_8k_to_16k(data)
    
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
        Konvertiert 24kHz 16-bit Audio zu 8kHz 8-bit unsigned PCM für pyVoIP.
        
        WICHTIG: pyVoIP erwartet RAW 8-bit unsigned PCM, NICHT A-law!
        pyVoIP encodiert selbst zu A-law/u-law basierend auf SDP-Aushandlung.
        
        Die AI sendet 24kHz 16-bit signed PCM.
        """
        if len(data) == 0:
            return b''
        
        try:
            source_rate = 24000
            target_rate = 8000
            
            # 1. Resample 24kHz -> 8kHz mit audioop
            resampled, _ = audioop.ratecv(data, 2, 1, source_rate, target_rate, None)
            
            # 2. Konvertiere 16-bit signed zu 8-bit unsigned
            # audioop.lin2lin(fragment, width_in, width_out)
            # Das konvertiert von 16-bit zu 8-bit (signed zu unsigned automatisch)
            pcm_8bit = audioop.lin2lin(resampled, 2, 1)
            
            return pcm_8bit
                
        except Exception as e:
            logger.warning(f"Audio-Konvertierung Fehler: {e}")
            return b''
    
    def _encode_output(self, samples: np.ndarray) -> bytes:
        """Enkodiert 16-bit samples im konfigurierten Output-Format."""
        # Default: A-law weil SDP 'preference': <PayloadType.PCMA: 8> zeigt
        codec = getattr(self, '_output_codec', 'alaw')
        bit_depth = getattr(self, '_output_bit_depth', 8)
        
        try:
            if codec == 'ulaw':
                return self._encode_ulaw(samples)
            elif codec == 'alaw':
                return self._encode_alaw(samples)
            elif bit_depth == 16:
                # 16-bit signed PCM
                return samples.astype(np.int16).tobytes()
            else:
                # 8-bit unsigned PCM (default)
                return bytes([max(0, min(255, (int(s) >> 8) + 128)) for s in samples])
        except Exception as e:
            logger.debug(f"Encoding Fehler: {e}")
            return b''
    
    def _encode_ulaw(self, samples: np.ndarray) -> bytes:
        """Enkodiert 16-bit PCM zu G.711 u-law."""
        BIAS = 0x84
        CLIP = 32635
        
        result = []
        for sample in samples:
            sample = int(sample)
            sign = 0
            if sample < 0:
                sign = 0x80
                sample = -sample
            
            if sample > CLIP:
                sample = CLIP
            
            sample += BIAS
            
            # Finde Exponent
            exponent = 7
            for exp in range(8):
                if sample < (1 << (exp + 8)):
                    exponent = exp
                    break
            
            mantissa = (sample >> (exponent + 3)) & 0x0F
            ulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
            result.append(ulaw_byte)
        
        return bytes(result)
    
    def _encode_alaw(self, samples: np.ndarray) -> bytes:
        """Enkodiert 16-bit PCM zu G.711 a-law."""
        result = []
        for sample in samples:
            sample = int(sample)
            sign = 0
            if sample < 0:
                sign = 0x80
                sample = -sample
            
            if sample > 32767:
                sample = 32767
            
            # Finde Exponent und Mantissa
            if sample < 256:
                exponent = 0
                mantissa = sample >> 4
            else:
                exponent = 1
                while sample >= (256 << exponent) and exponent < 7:
                    exponent += 1
                mantissa = (sample >> (exponent + 3)) & 0x0F
            
            alaw_byte = (sign | (exponent << 4) | mantissa) ^ 0x55
            result.append(alaw_byte)
        
        return bytes(result)
    
    def _detect_and_set_codec(self, call: Any) -> None:
        """
        Erkennt automatisch den Codec und Sample Rate aus der SDP-Nachricht
        und konfiguriert die Output-Einstellungen entsprechend.
        """
        try:
            codec_name = "alaw"  # Default
            sample_rate = 8000   # Default für G.711
            
            # Versuche Codec aus RTP preference zu lesen
            if hasattr(call, 'RTPClients') and call.RTPClients:
                rtp = call.RTPClients[0]
                
                # Log RTP Info
                logger.info(f"RTP: inIP={getattr(rtp, 'inIP', 'N/A')}, "
                           f"outIP={getattr(rtp, 'outIP', 'N/A')}, "
                           f"outPort={getattr(rtp, 'outPort', 'N/A')}")
                
                # Preference auslesen (z.B. <PayloadType.PCMA: 8>)
                if hasattr(rtp, 'preference'):
                    pref = rtp.preference
                    pref_str = str(pref).upper()
                    
                    if 'PCMA' in pref_str:
                        codec_name = "alaw"
                        logger.info("SDP: Erkannter Codec = A-law (PCMA)")
                    elif 'PCMU' in pref_str:
                        codec_name = "ulaw"
                        logger.info("SDP: Erkannter Codec = μ-law (PCMU)")
                    elif 'OPUS' in pref_str:
                        codec_name = "opus"
                        sample_rate = 48000
                        logger.info("SDP: Erkannter Codec = Opus (48kHz)")
                    elif 'G722' in pref_str:
                        codec_name = "g722"
                        sample_rate = 16000
                        logger.info("SDP: Erkannter Codec = G.722 (16kHz)")
                    else:
                        logger.info(f"SDP: Unbekannter Codec '{pref}', verwende A-law")
            
            # Versuche Sample Rate aus SDP Body zu lesen
            if hasattr(call, 'request') and call.request:
                body = getattr(call.request, 'body', None)
                if body and isinstance(body, dict):
                    media = body.get('m', [])
                    if media and len(media) > 0:
                        attrs = media[0].get('attributes', {})
                        # Suche nach dem aktiven Codec
                        for pt_id, pt_info in attrs.items():
                            rtpmap = pt_info.get('rtpmap', {})
                            name = rtpmap.get('name', '').upper()
                            freq = rtpmap.get('frequency')
                            
                            if codec_name == "alaw" and name == "PCMA":
                                if freq:
                                    sample_rate = int(freq)
                                    logger.info(f"SDP: PCMA Sample Rate = {sample_rate}Hz")
                                break
                            elif codec_name == "ulaw" and name == "PCMU":
                                if freq:
                                    sample_rate = int(freq)
                                    logger.info(f"SDP: PCMU Sample Rate = {sample_rate}Hz")
                                break
            
            # Setze die erkannten Einstellungen
            self._output_codec = codec_name
            self._output_sample_rate = sample_rate
            self._output_bit_depth = 8  # G.711 ist immer 8-bit encoded
            
            logger.info(f"=== AUTO-CONFIG: Codec={codec_name}, Rate={sample_rate}Hz ===")
            
            # Signal für UI (falls vorhanden)
            if hasattr(self._signals, 'codec_detected'):
                self._signals.codec_detected.emit(codec_name, sample_rate)
                
        except Exception as e:
            logger.warning(f"Codec-Erkennung fehlgeschlagen: {e}, verwende Default (A-law, 8kHz)")
            self._output_codec = "alaw"
            self._output_sample_rate = 8000
            self._output_bit_depth = 8

    def set_output_codec(self, codec: str) -> None:
        """Setzt den Output-Codec: 'pcm8', 'ulaw', 'alaw'"""
        self._output_codec = codec
        logger.info(f"Output-Codec gesetzt: {codec}")
    
    def set_output_settings(self, codec: str, sample_rate: int, bit_depth: int) -> None:
        """Setzt alle Output-Einstellungen."""
        self._output_codec = codec
        self._output_sample_rate = sample_rate
        self._output_bit_depth = bit_depth
        logger.info(f"Output-Einstellungen: {codec}, {sample_rate}Hz, {bit_depth}-bit")

    def enable_test_mode(self, audio_file: str, max_seconds: float = 10.0) -> bool:
        """
        Aktiviert Test-Modus: Spielt eine Audio-Datei ab statt AI zu verwenden.
        
        Args:
            audio_file: Pfad zur WAV-Datei (sollte 8kHz oder 24kHz sein)
            max_seconds: Maximale Länge in Sekunden (default: 10)
        
        Returns:
            True wenn erfolgreich geladen
        """
        import wave
        try:
            with wave.open(audio_file, 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                
                # Nur die ersten max_seconds laden
                max_frames = int(framerate * max_seconds)
                frames_to_read = min(n_frames, max_frames)
                frames = wf.readframes(frames_to_read)
                
            duration = frames_to_read / framerate
            logger.info(f"Test-Audio geladen: {audio_file}")
            logger.info(f"  Format: {framerate}Hz, {sample_width*8}-bit, {channels}ch")
            logger.info(f"  Länge: {duration:.1f}s ({len(frames)} bytes)")
            
            # Konvertiere zu Mono falls Stereo
            if channels == 2:
                samples = np.frombuffer(frames, dtype=np.int16)
                samples = samples[::2]  # Nur linken Kanal
                frames = samples.tobytes()
            
            self._test_audio_file = audio_file
            self._test_audio_data = frames
            self._test_audio_rate = framerate
            self._test_audio_width = sample_width
            self._test_mode = True
            
            logger.info(f"=== TEST-MODUS AKTIVIERT: {duration:.1f}s Audio ===")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Test-Audio: {e}")
            return False
    
    def restart_test_audio(self) -> None:
        """Startet Test-Audio von vorne."""
        self._test_audio_pos = 0
        self._test_audio_converted = None  # Wird beim nächsten Frame neu erstellt
        logger.info("Test-Audio zurückgesetzt - wird mit aktuellen Einstellungen neu vorbereitet")
    
    def disable_test_mode(self) -> None:
        """Deaktiviert Test-Modus."""
        self._test_mode = False
        self._test_audio_data = None
        if hasattr(self, '_test_audio_pos'):
            del self._test_audio_pos
        if hasattr(self, '_test_audio_converted'):
            del self._test_audio_converted
        logger.info("Test-Modus deaktiviert")
    
    def _prepare_test_audio(self) -> bytes:
        """
        Bereitet Test-Audio für SIP-Ausgabe vor.
        Konvertiert zu 8kHz 8-bit unsigned PCM für pyVoIP.
        
        WICHTIG: pyVoIP erwartet RAW 8-bit unsigned PCM, NICHT A-law!
        """
        if not self._test_audio_data:
            return b''
        
        try:
            sample_width = getattr(self, '_test_audio_width', 2)
            source_rate = getattr(self, '_test_audio_rate', 8000)
            target_rate = 8000
            
            # Audio-Daten als bytes
            audio_data = self._test_audio_data
            
            # Falls 8-bit unsigned, zu 16-bit signed konvertieren
            if sample_width == 1:
                audio_data = audioop.lin2lin(audio_data, 1, 2)
                sample_width = 2
            
            # Resample falls nötig mit audioop
            if source_rate != target_rate:
                audio_data, _ = audioop.ratecv(audio_data, sample_width, 1, source_rate, target_rate, None)
                logger.info(f"Test-Audio resampled: {source_rate}Hz -> {target_rate}Hz")
            
            # 16-bit signed zu 8-bit unsigned konvertieren (wie für AI Audio)
            pcm_8bit = audioop.lin2lin(audio_data, 2, 1)
            
            logger.info(f"Test-Audio vorbereitet: {len(pcm_8bit)} bytes (8kHz 8-bit unsigned)")
            return pcm_8bit
            
        except Exception as e:
            logger.error(f"Fehler bei Test-Audio Vorbereitung: {e}")
            return b''

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
            pcm_data: PCM Audio-Daten (24kHz, mono, 16-bit) von OpenAI API
        
        WICHTIG: pyVoIP braucht 160-byte Frames (20ms @ 8kHz, 8-bit).
        Die AI sendet aber größere Blöcke, die wir aufteilen müssen.
        """
        if not self._current_call or self._current_call.state != CallState.ACTIVE:
            return

        if not self._current_voip_call:
            return

        try:
            # 24kHz 16-bit -> 8kHz 8-bit unsigned PCM für pyVoIP
            converted = self._convert_16k_to_8k(pcm_data)
            
            if not converted:
                return
            
            # WICHTIG: In 160-byte Chunks aufteilen (20ms @ 8kHz, 8-bit)
            # pyVoIP erwartet exakte Frame-Größen!
            FRAME_SIZE = 160  # 20ms @ 8kHz, 8-bit
            
            for i in range(0, len(converted), FRAME_SIZE):
                chunk = converted[i:i + FRAME_SIZE]
                
                # Padding falls letzter Chunk zu klein
                if len(chunk) < FRAME_SIZE:
                    chunk = chunk + b'\x80' * (FRAME_SIZE - len(chunk))
                
                self._current_voip_call.write_audio(chunk)
                
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

    def _get_local_ip(self) -> str:
        """
        Ermittelt die lokale IP-Adresse für RTP.
        
        Versucht die beste nicht-lokale IP zu finden.
        """
        import socket
        
        try:
            # Verbinde zu externem Server um die richtige Interface-IP zu bekommen
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            # Verbinde zu einem externen Server (muss nicht erreichbar sein)
            s.connect((self._sip_config.server, 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            logger.warning(f"Konnte lokale IP nicht ermitteln: {e}")
            # Fallback
            try:
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except:
                return "0.0.0.0"

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
