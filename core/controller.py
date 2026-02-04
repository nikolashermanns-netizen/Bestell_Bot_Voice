"""
CallController - Zentrale Orchestrierung aller Komponenten.

Verbindet:
- SIP Client (Call Control)
- Audio Bridge (RTP <-> PCM)
- Realtime Client (AI)
- Audio Handler (Buffer <-> API)
- VAD (Interruption)
- Transcript Manager
"""

import logging
import threading
from typing import Optional
from datetime import datetime

from config import AppConfig
from core.state import AppState, CallState, RegistrationState
from core.signals import AppSignals
from core.audio_buffer import AudioBuffer
from sip.client import SIPClient, PJSUA2_AVAILABLE
from sip.audio_bridge import AudioBridge
from realtime_ai.client import RealtimeClient
from realtime_ai.audio_handler import AudioHandler
from realtime_ai.vad import VADDetector, InterruptionHandler
from transcription.manager import TranscriptManager
from core.local_audio import LocalAudioDevice, SOUNDDEVICE_AVAILABLE
from catalog.viega_catalog import ViegaCatalog

logger = logging.getLogger(__name__)


class CallController:
    """
    Zentrale Steuerung für Anrufe.

    Koordiniert alle Komponenten und steuert den Audio-Flow:

    ```
    SIP/RTP ─> AudioBridge ─> audio_in_buffer ─> AudioHandler ─> Realtime API
       ^                                                              │
       │                                                              v
       └─────── AudioBridge <── audio_out_buffer <── AudioHandler <───┘
    ```
    """

    def __init__(self, config: AppConfig, app_state: AppState, signals: AppSignals):
        """
        Initialisiert den CallController.

        Args:
            config: Anwendungskonfiguration
            app_state: Globaler App-State
            signals: Qt Signals für UI-Updates
        """
        self._config = config
        self._state = app_state
        self._signals = signals

        # Audio Buffer (klein halten für niedrige Latenz)
        self._audio_in_buffer = AudioBuffer(max_frames=15)  # ~300ms
        self._audio_out_buffer = AudioBuffer(max_frames=15)

        # Komponenten initialisieren
        self._sip_client: Optional[SIPClient] = None
        self._audio_bridge: Optional[AudioBridge] = None
        self._realtime_client: Optional[RealtimeClient] = None
        self._audio_handler: Optional[AudioHandler] = None
        self._vad: Optional[VADDetector] = None
        self._interrupt_handler: Optional[InterruptionHandler] = None
        self._transcript_manager: Optional[TranscriptManager] = None

        self._running = False
        self._debug_thread: Optional[threading.Thread] = None

        # Lokaler Audio-Modus
        self._local_audio: Optional[LocalAudioDevice] = None
        self._local_call_active = False

        # Viega Katalog
        self._catalog: Optional[ViegaCatalog] = None

        self._setup_components()
        self._connect_signals()

    def _setup_components(self) -> None:
        """Initialisiert alle Komponenten."""
        # SIP Client (optional wenn pjsua2 nicht verfügbar)
        if PJSUA2_AVAILABLE:
            self._sip_client = SIPClient(
                self._config.sip,
                self._config.audio,
                self._signals,
            )
        else:
            logger.warning("SIP Client nicht verfügbar - pjsua2 nicht installiert!")
            logger.warning("Eingehende Anrufe können nicht empfangen werden.")
            logger.warning("Bitte pjsua2 installieren für volle Funktionalität.")
            self._sip_client = None

        # Audio Bridge
        self._audio_bridge = AudioBridge(
            self._config.audio,
            self._audio_in_buffer,
            self._audio_out_buffer,
        )

        # Realtime Client
        self._realtime_client = RealtimeClient(
            self._config.openai,
            self._config.audio,
            self._signals,
        )

        # Audio Handler
        self._audio_handler = AudioHandler(
            self._config.audio,
            self._audio_in_buffer,
            self._audio_out_buffer,
            self._realtime_client,
        )

        # VAD und Interruption Handler
        self._vad = VADDetector()
        self._interrupt_handler = InterruptionHandler(
            self._vad,
            self._on_caller_interrupt,
        )

        # Transcript Manager
        self._transcript_manager = TranscriptManager(self._signals)

        # Lokales Audio-Gerät (für Tests ohne SIP)
        if SOUNDDEVICE_AVAILABLE:
            self._local_audio = LocalAudioDevice(
                self._config.audio,
                self._audio_in_buffer,
                self._audio_out_buffer,
            )
            logger.info("Lokales Audio verfügbar (Mikrofon/Lautsprecher)")
        else:
            self._local_audio = None

        # Viega Katalog laden
        try:
            self._catalog = ViegaCatalog()
            logger.info(f"Viega-Katalog geladen: {self._catalog.product_count} Produkte")
            
            # Katalog-Info an AI übergeben
            self._update_ai_with_catalog()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Katalogs: {e}")
            self._catalog = None
            logger.warning("sounddevice nicht verfügbar - kein lokaler Audio-Modus")

        logger.info("Alle Komponenten initialisiert")

    def _connect_signals(self) -> None:
        """Verbindet UI-Signale mit Controllern."""
        # UI Actions
        self._signals.action_accept_call.connect(self.accept_call)
        self._signals.action_reject_call.connect(self.reject_call)
        self._signals.action_hangup.connect(self.hangup)
        self._signals.action_mute_ai.connect(self.set_ai_muted)
        self._signals.action_change_model.connect(self.set_ai_model)

        # SIP Events
        self._signals.call_state_changed.connect(self._on_call_state_changed)

    def start(self) -> None:
        """Startet den Controller und registriert SIP."""
        if self._running:
            return

        self._running = True

        # SIP Registrierung starten (wenn verfügbar)
        if self._sip_client:
            self._sip_client.register()
            # Audio-Callback für SIP setzen
            self._sip_client.set_audio_callback(self._on_sip_audio_received)
            
            # Auto-Accept aktivieren (wenn konfiguriert)
            if self._config.auto_accept_calls:
                self._sip_client.set_auto_accept(True)
                self._sip_client.set_call_accepted_callback(self._on_sip_call_accepted)
                logger.info("Auto-Accept aktiviert - eingehende Anrufe werden automatisch angenommen")
        else:
            logger.warning("SIP nicht verfügbar - nur OpenAI Realtime API aktiv")

        # Debug Thread starten
        self._debug_thread = threading.Thread(
            target=self._debug_loop,
            name="CallController-Debug",
            daemon=True,
        )
        self._debug_thread.start()

        logger.info("CallController gestartet")

    def stop(self) -> None:
        """Stoppt den Controller und alle Komponenten."""
        self._running = False

        # Aktiven Anruf beenden
        if self._state.call_state == CallState.ACTIVE:
            self.hangup()

        # Komponenten stoppen
        if self._audio_handler:
            self._audio_handler.stop()

        if self._audio_bridge:
            self._audio_bridge.stop()

        if self._realtime_client:
            self._realtime_client.disconnect()

        if self._sip_client:
            self._sip_client.shutdown()

        logger.info("CallController gestoppt")

    @property
    def sip_available(self) -> bool:
        """Gibt zurück ob SIP verfügbar ist."""
        return self._sip_client is not None

    @property
    def local_audio_available(self) -> bool:
        """Gibt zurück ob lokales Audio verfügbar ist."""
        return self._local_audio is not None

    @property
    def catalog(self) -> Optional[ViegaCatalog]:
        """Gibt den Viega-Katalog zurück."""
        return self._catalog

    def _update_ai_with_catalog(self) -> None:
        """Aktualisiert die AI-Instruktionen mit dem Katalog."""
        if not self._catalog or not self._realtime_client:
            return
        
        # Basis-Instruktionen
        base_instructions = self._realtime_client._config.instructions
        
        # Kompakte Übersicht erstellen (nur Produkttypen, keine Details)
        context_summary = self._catalog.get_context_summary()
        
        # Kombinierte Instruktionen
        full_instructions = f"""{base_instructions}

{context_summary}
"""
        
        # An Realtime Client übergeben
        self._realtime_client.set_instructions(full_instructions)
        
        # Tool für Produktsuche registrieren
        from realtime_ai.client import PRODUCT_SEARCH_TOOL
        self._realtime_client.set_tools([PRODUCT_SEARCH_TOOL])
        
        # Function Call Handler registrieren
        self._realtime_client.set_function_call_callback(self._handle_function_call)
        
        logger.info("AI-Instruktionen mit Katalog aktualisiert (Function Calling aktiviert)")

    def _handle_function_call(self, function_name: str, arguments_json: str) -> str:
        """
        Verarbeitet Function Calls von der AI.
        
        Args:
            function_name: Name der Funktion
            arguments_json: JSON-String mit Argumenten
            
        Returns:
            Ergebnis als String
        """
        import json
        
        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError:
            return "Fehler: Ungültige Argumente"
        
        if function_name == "suche_produkt":
            return self._search_products(
                produkttyp=args.get("produkttyp", ""),
                groesse=args.get("groesse", ""),
                system=args.get("system", ""),
            )
        
        return f"Unbekannte Funktion: {function_name}"

    def _search_products(
        self,
        produkttyp: str,
        groesse: str = "",
        system: str = "",
    ) -> str:
        """
        Sucht Produkte im Katalog.
        
        Args:
            produkttyp: Produkttyp (z.B. "Bogen 90°", "Muffe")
            groesse: Größe in mm (optional)
            system: System/Werkstoff (optional)
            
        Returns:
            Formatierte Produktliste
        """
        if not self._catalog:
            return "Katalog nicht verfügbar"
        
        logger.info(f"Produktsuche: typ='{produkttyp}', groesse='{groesse}', system='{system}'")
        
        # Suche durchführen
        results = self._catalog.search(produkttyp)
        
        # Nach Größe filtern wenn angegeben
        if groesse:
            # Normalisiere Größe (z.B. "28mm" oder "28 mm" oder "28")
            groesse_clean = groesse.lower().replace(" ", "").replace("mm", "")
            results = [
                p for p in results
                if groesse_clean in p.groesse.lower().replace("mm", "") or
                   f"{groesse_clean}mm" in p.name.lower().replace(" ", "")
            ]
        
        # Nach System filtern wenn angegeben
        if system:
            system_lower = system.lower()
            results = [
                p for p in results
                if system_lower in p.werkstoff.lower() or
                   system_lower in p.gruppe.lower()
            ]
        
        if not results:
            # Zweiter Versuch ohne System-Filter
            if system:
                results = self._catalog.search(produkttyp)
                if groesse:
                    groesse_clean = groesse.lower().replace(" ", "").replace("mm", "")
                    results = [
                        p for p in results
                        if groesse_clean in p.groesse.lower().replace("mm", "") or
                           f"{groesse_clean}mm" in p.name.lower().replace(" ", "")
                    ]
        
        if not results:
            return f"Keine Produkte gefunden für: {produkttyp} {groesse}. Versuche andere Suchbegriffe."
        
        logger.info(f"Gefunden: {len(results)} Produkte")
        
        # Ergebnisse formatieren
        lines = [f"Gefundene Produkte ({len(results)}):", ""]
        for p in results[:10]:  # Max 10 Ergebnisse
            lines.append(f"- {p.name}")
            lines.append(f"  Art.Nr: {p.kennung} | Einheit: {p.einheit}")
        
        if len(results) > 10:
            lines.append(f"... und {len(results) - 10} weitere")
        
        return "\n".join(lines)

    def get_ai_instructions(self) -> str:
        """Gibt die aktuellen AI-Instruktionen zurück."""
        if self._realtime_client:
            return self._realtime_client._config.instructions
        return ""

    def start_local_call(
        self,
        input_device: Optional[int] = None,
        output_device: Optional[int] = None,
    ) -> bool:
        """
        Startet einen lokalen Test-Anruf mit Mikrofon/Lautsprecher.

        Args:
            input_device: ID des Mikrofons (None = Standard)
            output_device: ID des Lautsprechers (None = Standard)
            
        Returns:
            True wenn erfolgreich gestartet
        """
        if not self._local_audio:
            logger.error("Lokales Audio nicht verfügbar")
            self._signals.error_occurred.emit("Lokales Audio nicht verfügbar")
            return False

        if self._local_call_active:
            logger.warning("Lokaler Anruf bereits aktiv")
            return False

        if self._state.call_state == CallState.ACTIVE:
            logger.warning("Bereits ein Anruf aktiv")
            return False

        logger.info("Starte lokalen Test-Anruf...")

        # State aktualisieren
        self._state.start_call("Lokaler Test")
        self._state.accept_call()
        self._local_call_active = True

        # Lokales Audio starten mit ausgewählten Geräten
        self._local_audio.start(input_device=input_device, output_device=output_device)

        # Audio Handler starten
        self._audio_handler.start()

        # Realtime API verbinden
        self._realtime_client.connect()

        # Transkript starten
        self._transcript_manager.start_new_call()

        # UI aktualisieren
        self._signals.incoming_call.emit("Lokaler Test (Mikrofon)")
        self._signals.call_state_changed.emit(CallState.ACTIVE)

        logger.info("Lokaler Test-Anruf gestartet - sprich ins Mikrofon!")
        return True

    def stop_local_call(self) -> None:
        """Beendet den lokalen Test-Anruf."""
        if not self._local_call_active:
            return

        logger.info("Beende lokalen Test-Anruf...")

        self._local_call_active = False

        # Komponenten stoppen
        if self._audio_handler:
            self._audio_handler.stop()

        if self._local_audio:
            self._local_audio.stop()

        if self._realtime_client:
            self._realtime_client.disconnect()

        # State aktualisieren
        self._state.end_call()
        self._signals.call_state_changed.emit(CallState.ENDED)

        logger.info("Lokaler Test-Anruf beendet")

    def accept_call(self) -> None:
        """Nimmt den eingehenden Anruf an."""
        if self._state.call_state != CallState.RINGING:
            logger.warning("Kein eingehender Anruf zum Annehmen")
            return

        if not self._sip_client:
            logger.error("SIP Client nicht verfügbar")
            return

        # SIP Call annehmen
        if self._sip_client.accept_call():
            self._state.accept_call()

            # Audio-Verarbeitung starten
            self._start_audio_processing()

            # Realtime API verbinden
            self._realtime_client.connect()

            # Transkript starten
            self._transcript_manager.start_new_call()

            logger.info("Anruf angenommen")
        else:
            self._signals.error_occurred.emit("Fehler beim Annehmen des Anrufs")

    def reject_call(self) -> None:
        """Lehnt den eingehenden Anruf ab."""
        if self._state.call_state != CallState.RINGING:
            return

        if not self._sip_client:
            return

        if self._sip_client.reject_call():
            self._state.end_call()
            logger.info("Anruf abgelehnt")

    def hangup(self) -> None:
        """Beendet den aktiven Anruf."""
        if self._state.call_state not in [CallState.RINGING, CallState.ACTIVE]:
            return

        # Lokaler Anruf?
        if self._local_call_active:
            self.stop_local_call()
            return

        # Audio-Verarbeitung stoppen
        self._stop_audio_processing()

        # Realtime API trennen
        if self._realtime_client:
            self._realtime_client.disconnect()

        # SIP Call beenden
        if self._sip_client:
            self._sip_client.hangup()

        self._state.end_call()
        logger.info("Anruf beendet")

    def set_ai_muted(self, muted: bool) -> None:
        """Schaltet die AI-Audio stumm oder an."""
        self._state.ai_muted = muted

        if self._audio_handler:
            self._audio_handler.set_muted(muted)

        self._signals.ai_mute_changed.emit(muted)
        logger.info(f"AI {'stummgeschaltet' if muted else 'aktiviert'}")

    def set_ai_model(self, model: str) -> None:
        """
        Ändert das AI-Model.
        
        HINWEIS: Kann nur geändert werden wenn kein Anruf aktiv ist.
        Bei aktivem Anruf wird die Änderung ignoriert.
        
        Args:
            model: Model-Name (z.B. "gpt-4o-realtime-preview-2024-12-17" oder "gpt-realtime")
        """
        if self._state.call_state == CallState.ACTIVE:
            logger.warning("Model kann nicht während eines aktiven Anrufs geändert werden")
            self._signals.error_occurred.emit("Model-Änderung während Anruf nicht möglich")
            return
        
        if self._realtime_client:
            self._realtime_client.set_model(model)
            logger.info(f"AI-Model geändert zu: {model}")

    def get_ai_model(self) -> str:
        """Gibt das aktuelle AI-Model zurück."""
        if self._realtime_client:
            return self._realtime_client.get_model()
        return self._config.openai.model

    def _start_audio_processing(self) -> None:
        """Startet alle Audio-bezogenen Komponenten."""
        # Buffer starten
        self._audio_in_buffer.start()
        self._audio_out_buffer.start()

        # Audio Bridge starten
        self._audio_bridge.start()

        # Audio Handler starten
        self._audio_handler.start()

        # Audio Bridge Output-Callback setzen
        self._audio_bridge.set_sip_output_callback(
            lambda data: self._sip_client.send_audio(data)
        )

        logger.info("Audio-Verarbeitung gestartet")

    def _stop_audio_processing(self) -> None:
        """Stoppt alle Audio-bezogenen Komponenten."""
        if self._audio_handler:
            self._audio_handler.stop()

        if self._audio_bridge:
            self._audio_bridge.stop()

        self._audio_in_buffer.stop()
        self._audio_out_buffer.stop()

        logger.info("Audio-Verarbeitung gestoppt")

    def _on_sip_audio_received(self, pcm_data: bytes) -> None:
        """Callback für Audio vom SIP Stack."""
        # An Audio Bridge weiterleiten
        # HINWEIS: Das Audio vom pyVoIP SIP Client ist bereits 16kHz 16-bit PCM (L16)
        if self._audio_bridge:
            self._audio_bridge.receive_from_sip(pcm_data, codec="L16")

        # VAD für Interruption prüfen
        if self._vad:
            self._vad.process_frame(pcm_data)

    def _on_caller_interrupt(self) -> None:
        """Callback wenn Caller die AI unterbricht."""
        if self._state.ai_muted:
            return

        logger.info("Caller unterbricht AI")

        # AI-Antwort abbrechen
        if self._realtime_client:
            self._realtime_client.cancel_response()

        # Output-Buffer leeren
        self._audio_out_buffer.clear()

    def _on_sip_call_accepted(self) -> None:
        """
        Callback wenn ein SIP-Anruf angenommen wurde.
        
        Wird vom SIP Client aufgerufen nachdem der Anruf angenommen wurde
        (entweder manuell oder via Auto-Accept).
        Startet die Audio-Verarbeitung und AI-Verbindung.
        """
        logger.info("SIP-Anruf angenommen - starte Audio-Verarbeitung und AI...")
        
        # State aktualisieren
        self._state.accept_call()
        
        # Audio-Verarbeitung starten
        self._start_audio_processing()
        
        # Realtime API verbinden
        if self._realtime_client:
            self._realtime_client.connect()
        
        # Transkript starten
        if self._transcript_manager:
            self._transcript_manager.start_new_call()
        
        logger.info("Audio-Verarbeitung und AI gestartet")

    def _on_call_state_changed(self, state: CallState) -> None:
        """Handler für Call State Änderungen."""
        if state == CallState.ENDED:
            # Cleanup nach Anrufende
            self._stop_audio_processing()

            if self._realtime_client:
                self._realtime_client.disconnect()

    def _debug_loop(self) -> None:
        """Thread für periodische Debug-Updates."""
        import time

        while self._running:
            try:
                # Debug-Info sammeln
                info = self._collect_debug_info()

                # State aktualisieren
                self._state.debug.latency_ms = info.get("latency_ms", 0)
                self._state.debug.audio_in_queue_size = info.get("audio_in_queue", 0)
                self._state.debug.audio_out_queue_size = info.get("audio_out_queue", 0)

                # Signal emittieren
                self._signals.debug_updated.emit(info)

            except Exception as e:
                logger.error(f"Debug Loop Fehler: {e}")

            time.sleep(0.5)

    def _collect_debug_info(self) -> dict:
        """Sammelt Debug-Informationen von allen Komponenten."""
        info = {
            "audio_in_queue": self._audio_in_buffer.size,
            "audio_out_queue": self._audio_out_buffer.size,
            "latency_ms": self._estimate_latency(),
        }

        if self._audio_bridge:
            bridge_stats = self._audio_bridge.get_stats()
            info["bridge_stats"] = bridge_stats

        if self._audio_handler:
            handler_stats = self._audio_handler.get_stats()
            info["handler_stats"] = handler_stats

        return info

    def _estimate_latency(self) -> float:
        """Schätzt die aktuelle Latenz in Millisekunden."""
        # Einfache Schätzung basierend auf Buffer-Größen
        in_latency = self._audio_in_buffer.buffer_ms
        out_latency = self._audio_out_buffer.buffer_ms

        # API-Latenz schätzen (typisch 200-500ms)
        api_latency = 300.0

        return in_latency + out_latency + api_latency

    # === Öffentliche Properties ===

    @property
    def is_call_active(self) -> bool:
        """Gibt zurück ob ein Anruf aktiv ist."""
        return self._state.call_state == CallState.ACTIVE

    @property
    def is_registered(self) -> bool:
        """Gibt zurück ob SIP registriert ist."""
        return self._state.registration_state == RegistrationState.REGISTERED

    @property
    def transcript_manager(self) -> TranscriptManager:
        """Gibt den Transcript Manager zurück."""
        return self._transcript_manager



# Demo/Test
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from core.signals import init_signals

    app = QApplication(sys.argv)
    signals = init_signals()

    # Dummy Config (ohne echte Credentials)
    from config import SIPConfig, OpenAIConfig, AudioConfig

    config = AppConfig(
        sip=SIPConfig(server="test.local", username="test", password="test"),
        openai=OpenAIConfig(api_key="test"),
        audio=AudioConfig(),
    )
    state = AppState()

    controller = CallController(config, state, signals)

    # Signal Handler
    def on_call_state(state):
        print(f"Call State: {state.value}")

    def on_debug(info):
        print(f"Debug: in={info['audio_in_queue']}, out={info['audio_out_queue']}")

    signals.call_state_changed.connect(on_call_state)
    signals.debug_updated.connect(on_debug)

    # Starten
    print("Starte Controller...")
    controller.start()

    # Simuliere eingehenden Anruf nach 2 Sekunden
    QTimer.singleShot(2000, lambda: controller.simulate_incoming_call())

    # Event Loop für 10 Sekunden
    QTimer.singleShot(10000, app.quit)
    sys.exit(app.exec())
