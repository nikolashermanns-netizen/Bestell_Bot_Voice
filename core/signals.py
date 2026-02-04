"""
Qt Signals für thread-safe Kommunikation zwischen Komponenten.
"""

from PySide6.QtCore import QObject, Signal
from core.state import CallState, RegistrationState


class AppSignals(QObject):
    """
    Zentrale Signal-Sammlung für die Anwendung.

    Alle Cross-Thread Kommunikation läuft über diese Signals,
    um Thread-Safety mit Qt's Signal/Slot Mechanismus zu gewährleisten.
    """

    # === SIP Signals ===

    # Registrierungsstatus geändert (state, error_message)
    sip_registration_changed = Signal(RegistrationState, str)

    # Eingehender Anruf (caller_id)
    incoming_call = Signal(str)

    # Call State geändert (new_state)
    call_state_changed = Signal(CallState)

    # === AI Signals ===

    # AI Verbindungsstatus (connected)
    ai_connection_changed = Signal(bool)

    # AI Mute Status geändert (muted)
    ai_mute_changed = Signal(bool)

    # === Transkript Signals ===

    # Neuer Transkript-Text (speaker: "caller"|"assistant", text, is_final)
    transcript_updated = Signal(str, str, bool)

    # Transkript gelöscht
    transcript_cleared = Signal()

    # === Audio Signals ===

    # Audio-Level für Visualisierung (input_level, output_level) 0.0-1.0
    audio_levels = Signal(float, float)

    # === Debug Signals ===

    # Debug-Info aktualisiert (info_dict)
    debug_updated = Signal(dict)

    # Fehler aufgetreten (error_message)
    error_occurred = Signal(str)

    # === UI Actions (von UI zu Backend) ===

    # Anruf annehmen
    action_accept_call = Signal()

    # Anruf ablehnen
    action_reject_call = Signal()

    # Auflegen
    action_hangup = Signal()

    # AI stumm schalten (muted)
    action_mute_ai = Signal(bool)

    # AI Model ändern (model_name)
    action_change_model = Signal(str)


# Globale Signal-Instanz
# Wird in main.py erstellt und an alle Komponenten weitergegeben
_signals: AppSignals | None = None


def get_signals() -> AppSignals:
    """
    Gibt die globale Signal-Instanz zurück.

    Returns:
        AppSignals Instanz

    Raises:
        RuntimeError: Wenn Signals noch nicht initialisiert
    """
    global _signals
    if _signals is None:
        raise RuntimeError("AppSignals noch nicht initialisiert. Rufe init_signals() zuerst auf.")
    return _signals


def init_signals() -> AppSignals:
    """
    Initialisiert die globale Signal-Instanz.

    Returns:
        Neue AppSignals Instanz
    """
    global _signals
    _signals = AppSignals()
    return _signals


# Demo/Test
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    signals = init_signals()

    # Test: Signal verbinden
    def on_call_state(state: CallState):
        print(f"Call state changed to: {state.value}")

    def on_transcript(speaker: str, text: str, is_final: bool):
        final_marker = "[FINAL]" if is_final else "[partial]"
        print(f"{final_marker} {speaker}: {text}")

    signals.call_state_changed.connect(on_call_state)
    signals.transcript_updated.connect(on_transcript)

    # Test: Signals emittieren
    print("Emitting test signals...")
    signals.call_state_changed.emit(CallState.RINGING)
    signals.call_state_changed.emit(CallState.ACTIVE)
    signals.transcript_updated.emit("caller", "Hallo, ich möchte", False)
    signals.transcript_updated.emit("caller", "Hallo, ich möchte bestellen", True)
    signals.transcript_updated.emit("assistant", "Guten Tag! Was darf es sein?", True)

    print("\nSignals test complete!")
